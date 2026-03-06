"""
职探AI Web 应用入口。

功能:
1. 主页面展示三个模块: 查看报告、开始对话、Boss 登录
2. 对话触发搜索 -> 分析 -> 出报告完整流程
3. 管理和查看历史报告
"""

from __future__ import annotations

import json
import importlib
import os
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

import requests
from flask import Flask, jsonify, render_template, request, send_file

from src.analyzer import JobAnalyzer
from src.config import Config
from src.models import CITY_CODES, SearchQuery
from src.report import ReportGenerator
from src.scraper import BossZhipinScraper

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, template_folder="template", static_folder="static")

TASK_LOCK = threading.Lock()
CHAT_TASKS: Dict[str, Dict[str, Any]] = {}


@dataclass
class ChatIntent:
    """对话指令意图。"""

    action: str
    keyword: str
    city: str
    pages: int


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _collect_report_files() -> List[Dict[str, Any]]:
    cfg = Config.load()
    output_dir = BASE_DIR / cfg.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    items: List[Dict[str, Any]] = []
    for file_path in output_dir.glob("report_*"):
        if file_path.suffix.lower() not in {".md", ".html", ".pdf"}:
            continue
        stat = file_path.stat()
        items.append(
            {
                "name": file_path.name,
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "suffix": file_path.suffix.lower(),
            }
        )

    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def _render_markdown_to_html(content: str) -> str:
    """将 Markdown 渲染为 HTML，若依赖缺失则返回空字符串。"""
    try:
        md_module = importlib.import_module("markdown")
    except Exception:
        return ""

    return md_module.markdown(
        content,
        extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
    )


def _ask_llm_for_intent(config: Config, message: str) -> ChatIntent | None:
    """在配置了 AI Key 时，尝试让模型把自然语言转为结构化查询。"""
    if not config.ai_api_key:
        return None

    base_url = config.ai_base_url.rstrip("/")
    if not base_url.endswith("/chat/completions"):
        base_url = f"{base_url}/chat/completions"

    city_list = "、".join(CITY_CODES.keys())
    prompt = (
        "你是职位搜索助手，请把用户请求解析成 JSON。"
        "只返回 JSON，不要解释。"
        "字段: action(search|recommend), keyword, city, pages。"
        f"city 必须从这些城市里选择: {city_list}。"
        "pages 必须是 1 到 5 的整数。"
        "如果用户没有明确关键词，keyword 用空字符串。"
        f"用户输入: {message}"
    )

    payload = {
        "model": config.ai_model,
        "messages": [
            {"role": "system", "content": "你只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.ai_api_key}",
    }

    try:
        resp = requests.post(base_url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        action = parsed.get("action", "search")
        city = parsed.get("city", "北京")
        pages = max(1, min(5, _safe_int(parsed.get("pages"), 2)))
        keyword = str(parsed.get("keyword", "")).strip()

        if city not in CITY_CODES:
            city = "北京"

        if action not in {"search", "recommend"}:
            action = "search"

        return ChatIntent(action=action, keyword=keyword, city=city, pages=pages)
    except Exception:
        return None


def _fallback_intent(message: str) -> ChatIntent:
    """无需 AI 的规则解析。"""
    text = message.strip()
    text_lower = text.lower()

    action = "recommend" if ("推荐" in text or "recommend" in text_lower) else "search"

    city = "北京"
    for city_name in CITY_CODES.keys():
        if city_name in text:
            city = city_name
            break

    pages = 2
    page_match = re.search(r"(\d+)\s*页", text)
    if page_match:
        pages = max(1, min(5, _safe_int(page_match.group(1), 2)))

    keyword = ""
    keyword_match = re.search(r"(?:搜索|查找|分析|查询|找)\s*([\u4e00-\u9fa5A-Za-z0-9+#\.\-]+)", text)
    if keyword_match:
        keyword = keyword_match.group(1).strip()

    if not keyword and action == "search":
        cleaned = text
        for token in ["请", "帮我", "一下", "岗位", "职位", "工作", "搜索", "查找", "分析", "查询", "找"]:
            cleaned = cleaned.replace(token, "")
        cleaned = cleaned.strip(" ，,。.!！?？")
        keyword = cleaned[:30] if cleaned else "Python开发"

    return ChatIntent(action=action, keyword=keyword, city=city, pages=pages)


def _parse_intent(config: Config, message: str) -> ChatIntent:
    intent = _ask_llm_for_intent(config, message)
    if intent is not None:
        return intent
    return _fallback_intent(message)


def _extract_user_profile(message: str) -> Dict[str, Any]:
    """从自由输入中提取用户经历与诉求，用于个性化分析。"""
    text = str(message or "").strip()
    if not text:
        return {}

    profile: Dict[str, Any] = {
        "years_of_experience": None,
        "goals": [],
        "strengths": [],
        "concerns": [],
        "personal_notes": [],
    }

    year_match = re.search(r"(\d+(?:\.\d+)?)\s*年", text)
    if year_match:
        profile["years_of_experience"] = year_match.group(1)

    sentences = [x.strip() for x in re.split(r"[。！？!\?；;\n]+", text) if x.strip()]
    goal_markers = ("想", "希望", "目标", "打算", "计划", "转行", "冲", "拿到")
    strength_markers = ("擅长", "熟悉", "做过", "负责", "经验", "会", "掌握")
    concern_markers = ("担心", "不会", "薄弱", "缺乏", "没做过", "焦虑", "压力", "卡")
    personal_markers = ("我", "自己", "目前", "之前", "毕业", "经历", "项目", "工作")

    def _append_unique(key: str, sentence: str, limit: int) -> None:
        if sentence not in profile[key] and len(profile[key]) < limit:
            profile[key].append(sentence)

    for sent in sentences:
        if any(k in sent for k in personal_markers):
            _append_unique("personal_notes", sent[:120], 6)
        if any(k in sent for k in goal_markers):
            _append_unique("goals", sent[:100], 4)
        if any(k in sent for k in strength_markers):
            _append_unique("strengths", sent[:100], 4)
        if any(k in sent for k in concern_markers):
            _append_unique("concerns", sent[:100], 4)

    # 剔除空项，减小在模型提示中的噪声。
    compact_profile = {k: v for k, v in profile.items() if v}
    return compact_profile


def _profile_summary_text(profile: Dict[str, Any]) -> str:
    if not profile:
        return "未检测到可用个人经历信息。"

    parts = []
    if profile.get("years_of_experience"):
        parts.append(f"经验约{profile['years_of_experience']}年")
    if profile.get("goals"):
        parts.append(f"目标: {profile['goals'][0]}")
    if profile.get("concerns"):
        parts.append(f"顾虑: {profile['concerns'][0]}")
    return " | ".join(parts) if parts else "已提取到个人经历信息。"


def _new_task_record(message: str) -> str:
    task_id = uuid.uuid4().hex
    with TASK_LOCK:
        CHAT_TASKS[task_id] = {
            "id": task_id,
            "ok": None,
            "status": "running",
            "progress": 0,
            "stage": "queued",
            "message": "任务已创建，准备开始...",
            "user_message": message,
            "result": None,
        }
    return task_id


def _update_task(
    task_id: str,
    *,
    progress: int | None = None,
    stage: str | None = None,
    message: str | None = None,
    status: str | None = None,
    ok: bool | None = None,
    result: Dict[str, Any] | None = None,
) -> None:
    with TASK_LOCK:
        task = CHAT_TASKS.get(task_id)
        if not task:
            return
        if progress is not None:
            task["progress"] = max(0, min(100, int(progress)))
        if stage is not None:
            task["stage"] = stage
        if message is not None:
            task["message"] = message
        if status is not None:
            task["status"] = status
        if ok is not None:
            task["ok"] = ok
        if result is not None:
            task["result"] = result


def _get_task(task_id: str) -> Dict[str, Any] | None:
    with TASK_LOCK:
        task = CHAT_TASKS.get(task_id)
        return dict(task) if task else None


def _run_pipeline(message: str, progress_cb: Callable[[int, str, str], None] | None = None) -> Dict[str, Any]:
    def step(pct: int, stage: str, text: str) -> None:
        if progress_cb:
            progress_cb(pct, stage, text)

    config = Config.load()
    if not config.cookie:
        return {
            "ok": False,
            "message": "还没有 Boss Cookie，请先在【Boss登录】板块保存 Cookie 后再开始对话。",
        }

    if config.ai_api_key:
        step(3, "ai.intent.start", "正在调用 AI 进行意图解析...")
    else:
        step(3, "rule.intent.start", "未配置 AI，正在使用规则解析意图...")

    intent = _parse_intent(config, message)

    if config.ai_api_key:
        step(8, "ai.intent.done", "AI 意图解析完成，正在提取你的个人经历信息...")
    else:
        step(8, "rule.intent.done", "规则意图解析完成，正在提取你的个人经历信息...")
    user_profile = _extract_user_profile(message)
    step(12, "profile", f"已提取个人信息: {_profile_summary_text(user_profile)}")

    scraper = BossZhipinScraper(config)
    analyzer = JobAnalyzer(config)
    reporter = ReportGenerator(config)

    step(16, "prepare", "正在准备抓取任务，过程可能需要几十秒...")
    report_snapshot = {x["name"] for x in _collect_report_files()}

    def on_scrape_progress(done_pages: int, total_pages: int, job_count: int) -> None:
        total_pages = max(total_pages, 1)
        pct = 18 + int((done_pages / total_pages) * 36)
        step(
            pct,
            "scraping.page",
            f"正在抓取职位数据: {done_pages}/{total_pages} 页, 已获取 {job_count} 条。网络波动时会稍慢，这是正常现象。",
        )

    if intent.action == "recommend":
        jobs = scraper.get_recommend_jobs(max_pages=intent.pages, progress_callback=on_scrape_progress)
        query_name = "推荐职位"
    else:
        query = SearchQuery(
            keyword=intent.keyword,
            city=CITY_CODES.get(intent.city, CITY_CODES["北京"]),
            city_name=intent.city,
            max_pages=intent.pages,
        )
        jobs = scraper.search_jobs(query, progress_callback=on_scrape_progress)
        query_name = intent.keyword

    if not jobs:
        return {
            "ok": False,
            "message": "没有抓取到有效职位数据。请检查关键词、城市或登录状态后重试。",
        }

    step(58, "save-data", "抓取完成，正在保存原始数据...")
    data_path = scraper.save_jobs(jobs)

    def on_analyze_progress(local_pct: int, stage: str, msg: str) -> None:
        mapped = 60 + int(max(0, min(100, local_pct)) * 0.22)
        step(mapped, stage, msg)

    step(62, "analyzing.start", "开始深度分析，这一步会做多维统计与个性化建议生成...")
    analysis = analyzer.analyze(
        jobs,
        query=query_name,
        user_profile=user_profile,
        progress_callback=on_analyze_progress,
    )

    def on_report_progress(local_pct: int, stage: str, msg: str) -> None:
        mapped = 84 + int(max(0, min(100, local_pct)) * 0.14)
        step(mapped, stage, msg)

    step(84, "report.start", "正在生成 PDF 报告，请稍等，排版阶段可能略久...")
    reporter.generate_pdf(analysis, jobs, save=True, progress_callback=on_report_progress)
    step(99, "finalizing", "报告生成完毕，正在整理结果...")

    report_after = _collect_report_files()
    new_reports = [x for x in report_after if x["name"] not in report_snapshot]
    latest_report = (new_reports[0]["name"] if new_reports else report_after[0]["name"])

    summary = (
        f"任务完成: 已执行{intent.action}流程, 共抓取 {len(jobs)} 条职位, "
        f"并生成报告 `{latest_report}`。"
    )

    return {
        "ok": True,
        "message": summary,
        "intent": {
            "action": intent.action,
            "keyword": intent.keyword,
            "city": intent.city,
            "pages": intent.pages,
        },
        "jobs_count": len(jobs),
        "user_profile": user_profile,
        "user_profile_summary": _profile_summary_text(user_profile),
        "data_file": os.path.basename(data_path),
        "report_file": latest_report,
    }


def _run_pipeline_task(task_id: str, message: str) -> None:
    def progress_cb(pct: int, stage: str, text: str) -> None:
        _update_task(task_id, progress=pct, stage=stage, message=text)

    try:
        result = _run_pipeline(message, progress_cb=progress_cb)
        if result.get("ok"):
            _update_task(
                task_id,
                progress=100,
                stage="done",
                message="任务完成",
                status="done",
                ok=True,
                result=result,
            )
        else:
            _update_task(
                task_id,
                stage="failed",
                message=result.get("message", "任务失败"),
                status="failed",
                ok=False,
                result=result,
            )
    except Exception as e:
        _update_task(
            task_id,
            stage="failed",
            message=f"执行异常: {e}",
            status="failed",
            ok=False,
            result={"ok": False, "message": f"执行异常: {e}"},
        )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def api_status():
    cfg = Config.load()
    return jsonify(
        {
            "ok": True,
            "has_cookie": bool(cfg.cookie),
            "ai_configured": bool(cfg.ai_api_key),
            "ai_model": cfg.ai_model,
        }
    )


@app.get("/api/reports")
def api_reports():
    return jsonify({"ok": True, "reports": _collect_report_files()})


@app.get("/api/reports/<path:report_name>")
def api_report_content(report_name: str):
    cfg = Config.load()
    output_dir = (BASE_DIR / cfg.output_dir).resolve()
    target = (output_dir / report_name).resolve()

    if output_dir not in target.parents or not target.exists():
        return jsonify({"ok": False, "message": "报告不存在"}), 404

    suffix = target.suffix.lower()

    if suffix == ".pdf":
        return jsonify(
            {
                "ok": True,
                "name": report_name,
                "suffix": suffix,
                "is_binary": True,
                "view_url": f"/api/reports/{report_name}/raw",
            }
        )

    content = target.read_text(encoding="utf-8")
    rendered_html = _render_markdown_to_html(content) if suffix == ".md" else ""

    return jsonify(
        {
            "ok": True,
            "name": report_name,
            "suffix": suffix,
            "content": content,
            "rendered_html": rendered_html,
            "is_binary": False,
        }
    )


@app.get("/api/reports/<path:report_name>/raw")
def api_report_raw(report_name: str):
    cfg = Config.load()
    output_dir = (BASE_DIR / cfg.output_dir).resolve()
    target = (output_dir / report_name).resolve()

    if output_dir not in target.parents or not target.exists():
        return jsonify({"ok": False, "message": "报告不存在"}), 404

    return send_file(target)


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"ok": False, "message": "消息不能为空"}), 400

    task_id = _new_task_record(message)
    worker = threading.Thread(target=_run_pipeline_task, args=(task_id, message), daemon=True)
    worker.start()

    return jsonify({"ok": True, "task_id": task_id, "message": "任务已启动"})


@app.get("/api/chat/task/<task_id>")
def api_chat_task(task_id: str):
    task = _get_task(task_id)
    if not task:
        return jsonify({"ok": False, "message": "任务不存在"}), 404
    return jsonify({"ok": True, "task": task})


@app.post("/api/boss/login-save")
def api_boss_login_save():
    payload = request.get_json(silent=True) or {}
    cookie = str(payload.get("cookie", "")).strip()
    bst = str(payload.get("bst", "")).strip()

    if not cookie:
        return jsonify({"ok": False, "message": "Cookie 不能为空"}), 400

    cfg = Config.load()
    cfg.cookie = cookie
    cfg.bst = bst
    cfg.save()

    return jsonify({"ok": True, "message": "Boss Cookie 已保存"})


@app.post("/api/boss/login-mcp")
def api_boss_login_mcp():
    cfg = Config.load()
    scraper = BossZhipinScraper(cfg)
    success = scraper.load_cookie_from_mcp()

    if success:
        return jsonify({"ok": True, "message": "MCP 登录成功，Cookie 已更新"})
    return jsonify({"ok": False, "message": "MCP 登录失败，请查看终端日志"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
