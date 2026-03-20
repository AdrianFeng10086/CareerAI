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
import time
import threading
import uuid
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

import requests
from flask import Flask, jsonify, render_template, request, send_file, Response

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Random import get_random_bytes

from src.analyzer import JobAnalyzer
from src.config import Config
from src.models import CITY_CODES, SearchQuery
from src.report import ReportGenerator
from src.scraper import BossZhipinScraper
from src.boss_zp.cookie_utils import save_cookie_to_config

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, template_folder="template", static_folder="static")

TASK_LOCK = threading.Lock()
CHAT_TASKS: Dict[str, Dict[str, Any]] = {}
MCP_LOGIN_LOCK = threading.Lock()
MCP_LOGIN_TASKS: Dict[str, Dict[str, Any]] = {}


@dataclass
class ChatIntent:
    """对话指令意图。"""

    action: str
    keyword: str
    city: str
    pages: int
    personal_strengths_summary: str = ""
    intent_provider: str = ""


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_json_block(text: str) -> Dict[str, Any]:
    """从模型返回文本中提取 JSON 对象，兼容代码块包裹。"""
    raw = str(text or "").strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    if "```" in raw:
        candidate = raw
        candidate = re.sub(r"^```(?:json)?\\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\\s*```$", "", candidate)
        candidate = candidate.strip()
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    return {}


def _build_chat_completions_url(base_url: str) -> str:
    """将配置中的 base_url 规范化为 chat/completions 完整地址。"""
    url = str(base_url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/chat/completions"


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
    if not config.ai_api_key and not config.backup_ai_api_key:
        return None

    providers = [
        {
            "name": "主AI",
            "api_key": config.ai_api_key,
            "base_url": _build_chat_completions_url(config.ai_base_url),
            "model": config.ai_model,
            "enable_enhancement": False,
        }
    ]
    if config.backup_ai_api_key:
        providers.append(
            {
                "name": "备用AI",
                "api_key": config.backup_ai_api_key,
                "base_url": _build_chat_completions_url(config.backup_ai_base_url),
                "model": config.backup_ai_model,
                "enable_enhancement": bool(config.backup_ai_enable_enhancement),
            }
        )

    city_list = "、".join(CITY_CODES.keys())
    prompt = (
        "你是职位搜索助手，请把用户请求解析成 JSON。"
        "只返回 JSON，不要解释。"
        "字段: action(search|recommend), keyword, city, pages, personal_strengths_summary。"
        f"city 必须从这些城市里选择: {city_list}。"
        "pages 必须是 1 到 5 的整数。"
        "如果用户没有明确关键词，keyword 用空字符串。"
        "personal_strengths_summary 用 60-120 字中文总结用户输入中体现的个人优势；"
        "如果无法判断，返回空字符串。"
        f"用户输入: {message}"
    )

    try:
        from requests.exceptions import ConnectionError, Timeout, ChunkedEncodingError

        parsed: Dict[str, Any] = {}
        selected_provider = ""
        for p_idx, provider in enumerate(providers):
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {provider['api_key']}",
            }
            payload = {
                "model": provider["model"],
                "messages": [
                    {"role": "system", "content": "你只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 200,
            }
            if provider.get("enable_enhancement"):
                payload["enable_enhancement"] = True

            max_attempts = 3
            provider_success = False
            for attempt in range(1, max_attempts + 1):
                try:
                    resp = requests.post(provider["base_url"], json=payload, headers=headers, timeout=(10, 25))
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = _extract_json_block(content)
                    if parsed:
                        provider_success = True
                        break
                except (ConnectionError, Timeout, ChunkedEncodingError):
                    if attempt >= max_attempts:
                        break
                    time.sleep(0.8 * attempt)
                except requests.HTTPError as e:
                    status_code = getattr(e.response, "status_code", 0)
                    if status_code in {429, 500, 502, 503, 504}:
                        if attempt < max_attempts:
                            time.sleep(0.8 * attempt)
                            continue
                        break
                    return None

            if provider_success and parsed:
                selected_provider = str(provider.get("name", ""))
                break

            has_next = p_idx < len(providers) - 1
            if has_next:
                continue

        if not parsed:
            return None

        action = parsed.get("action", "search")
        city = parsed.get("city", "北京")
        pages = max(1, min(5, _safe_int(parsed.get("pages"), 2)))
        keyword = str(parsed.get("keyword", "")).strip()
        personal_strengths_summary = str(parsed.get("personal_strengths_summary", "")).strip()
        personal_strengths_summary = personal_strengths_summary[:220]

        if city not in CITY_CODES:
            city = "北京"

        if action not in {"search", "recommend"}:
            action = "search"

        return ChatIntent(
            action=action,
            keyword=keyword,
            city=city,
            pages=pages,
            personal_strengths_summary=personal_strengths_summary,
            intent_provider=selected_provider,
        )
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

    return ChatIntent(action=action, keyword=keyword, city=city, pages=pages, intent_provider="规则解析")


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
        "education_level": "",
        "target_city": "",
        "target_role": "",
        "research_focus": [],
        "projects": [],
        "achievements": [],
        "tech_stack": [],
        "goals": [],
        "strengths": [],
        "concerns": [],
        "personal_notes": [],
    }

    year_match = re.search(r"(\d+(?:\.\d+)?)\s*年", text)
    if year_match:
        profile["years_of_experience"] = year_match.group(1)

    edu_match = re.search(r"(博士|硕士|研究生|本科|大专|中专|高中|985|211|一本|二本|专升本)", text)
    if edu_match:
        profile["education_level"] = edu_match.group(1)

    for city_name in CITY_CODES.keys():
        if city_name in text:
            profile["target_city"] = city_name
            break

    role_match = re.search(
        r"(?:找|应聘|求职|投递|冲|面向)\s*(?:一个|一份|岗位|职位)?\s*([\u4e00-\u9fa5A-Za-z0-9+\-#/]{2,30})\s*(?:岗|岗位|职位)?",
        text,
    )
    if role_match:
        profile["target_role"] = role_match.group(1).strip(" ，,。；;：:")

    focus_patterns = [
        r"研究方向[为是:]?\s*([^。；;\n]{4,80})",
        r"主要研究方向[为是:]?\s*([^。；;\n]{4,80})",
        r"长期关注\s*([^。；;\n]{4,80})",
    ]
    for pattern in focus_patterns:
        for m in re.findall(pattern, text):
            val = str(m).strip(" ：:，,。；;")
            if val and val not in profile["research_focus"] and len(profile["research_focus"]) < 5:
                profile["research_focus"].append(val)

    sentences = [x.strip() for x in re.split(r"[。！？!\?；;\n]+", text) if x.strip()]
    goal_markers = ("想", "希望", "目标", "打算", "计划", "转行", "冲", "拿到")
    strength_markers = (
        "擅长", "熟悉", "做过", "负责", "经验", "会", "掌握", "具备", "能够", "实现",
        "构建", "开发", "优化", "落地", "实践", "原型", "开源", "RAG", "Agent",
    )
    concern_markers = ("担心", "不会", "薄弱", "缺乏", "没做过", "焦虑", "压力", "卡")
    personal_markers = (
        "我", "自己", "目前", "之前", "毕业", "经历", "项目", "工作", "研究方向", "关注", "获奖", "竞赛",
    )
    project_markers = ("项目", "系统", "平台", "原型", "问诊", "客服", "uni-app", "vue", "github")
    achievement_markers = ("获奖", "一等奖", "二等奖", "三等奖", "挑战杯", "泰迪杯", "竞赛", "开源")
    tech_terms = [
        "RAG", "AI Agent", "Agent", "LLM", "大语言模型", "Prompt", "向量检索", "知识库", "Python",
        "Vue2", "Vue", "uni-app", "Multi-Agent", "GitHub",
    ]

    def _append_unique(key: str, sentence: str, limit: int) -> None:
        if sentence not in profile[key] and len(profile[key]) < limit:
            profile[key].append(sentence)

    for sent in sentences:
        if any(k in sent for k in personal_markers):
            _append_unique("personal_notes", sent[:260], 8)
        if any(k in sent for k in goal_markers):
            _append_unique("goals", sent[:220], 6)
        if any(k in sent for k in strength_markers):
            _append_unique("strengths", sent[:280], 8)
        if any(k in sent for k in concern_markers):
            _append_unique("concerns", sent[:220], 6)
        if any(k.lower() in sent.lower() for k in project_markers):
            _append_unique("projects", sent[:260], 8)
        if any(k in sent for k in achievement_markers):
            _append_unique("achievements", sent[:220], 8)

    lower_text = text.lower()
    for term in tech_terms:
        if term.lower() in lower_text and term not in profile["tech_stack"]:
            profile["tech_stack"].append(term)
    profile["tech_stack"] = profile["tech_stack"][:15]

    if not any(v for v in profile.values() if v):
        # 极端情况下兜底，避免长文本被判空。
        fallback_notes = [x.strip() for x in re.split(r"[\n]+", text) if x.strip()][:3]
        profile["personal_notes"] = [x[:120] for x in fallback_notes]

    # 剔除空项，减小在模型提示中的噪声。
    compact_profile = {k: v for k, v in profile.items() if v}
    return compact_profile


def _profile_summary_text(profile: Dict[str, Any]) -> str:
    if not profile:
        return "未检测到可用个人经历信息。"

    parts = []
    if profile.get("education_level"):
        parts.append(f"学历/背景: {profile['education_level']}")
    if profile.get("years_of_experience"):
        parts.append(f"经验约{profile['years_of_experience']}年")
    if profile.get("target_city"):
        parts.append(f"期望城市: {profile['target_city']}")
    if profile.get("target_role"):
        parts.append(f"方向: {profile['target_role']}")
    if profile.get("goals"):
        parts.append(f"目标: {profile['goals'][0]}")
    if profile.get("research_focus"):
        parts.append(f"研究重点: {profile['research_focus'][0]}")
    if profile.get("projects"):
        parts.append(f"项目经历: {len(profile['projects'])}条")
    if profile.get("tech_stack"):
        parts.append(f"技术栈: {', '.join(profile['tech_stack'][:3])}")
    if profile.get("personal_strengths_summary"):
        parts.append(f"优势总结: {profile['personal_strengths_summary'][:60]}")
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
            "events": [],
            "next_event_id": 1,
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
        if not task:
            return None
        snapshot = dict(task)
        snapshot["events"] = list(task.get("events", []))
        return snapshot


def _new_mcp_login_task() -> str:
    task_id = uuid.uuid4().hex
    with MCP_LOGIN_LOCK:
        MCP_LOGIN_TASKS[task_id] = {
            "id": task_id,
            "status": "running",
            "ok": None,
            "step": "starting",
            "message": "正在初始化 MCP 登录流程...",
            "qr_id": "",
            "qr_ready": False,
            "qr_bytes": b"",
            "started_at": int(time.time()),
            "updated_at": int(time.time()),
        }
    return task_id


def _update_mcp_login_task(task_id: str, **kwargs: Any) -> None:
    with MCP_LOGIN_LOCK:
        task = MCP_LOGIN_TASKS.get(task_id)
        if not task:
            return
        for k, v in kwargs.items():
            task[k] = v
        task["updated_at"] = int(time.time())


def _get_mcp_login_task(task_id: str) -> Dict[str, Any] | None:
    with MCP_LOGIN_LOCK:
        task = MCP_LOGIN_TASKS.get(task_id)
        if not task:
            return None
        snapshot = dict(task)
        snapshot.pop("qr_bytes", None)
        return snapshot


def _get_mcp_qr_bytes(task_id: str) -> bytes:
    with MCP_LOGIN_LOCK:
        task = MCP_LOGIN_TASKS.get(task_id) or {}
        return task.get("qr_bytes", b"")


def _generate_boss_fp() -> str:
    i_str = "8048b8676fb7d3d8952276e6e98e0bde.f2dc7a63c4b0fbfa4b51a07e2710cf83.fef7e750fc3a1e6327e8a880915aee9c.ae00f848beb1aa591d71d5a80dd3bd95"
    e_b64 = "clRwXUJBK1VKK0k0IWFbbQ=="

    key_bytes = base64.b64decode(e_b64)
    plaintext_bytes = i_str.encode("utf-8")
    iv_bytes = get_random_bytes(16)
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
    padded_plaintext = pad(plaintext_bytes, AES.block_size)
    ciphertext_bytes = cipher.encrypt(padded_plaintext)
    result_bytes = iv_bytes + ciphertext_bytes
    return base64.b64encode(result_bytes).decode("utf-8")


def _parse_set_cookie(set_cookie_headers: str) -> tuple[str, str]:
    cookie_str = ""
    bst_value = ""
    if not set_cookie_headers:
        return cookie_str, bst_value

    cookies: Dict[str, str] = {}
    cookie_parts = set_cookie_headers.split(",")
    for part in cookie_parts:
        if "=" not in part:
            continue
        name_value = part.strip().split(";", 1)[0].strip()
        if "=" not in name_value:
            continue
        name, value = name_value.split("=", 1)
        cookies[name.strip()] = value.strip()

    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    if "bst" in cookies:
        bst_value = cookies["bst"]
    return cookie_str, bst_value


def _run_mcp_login_task(task_id: str) -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.zhipin.com/web/user/?ka=header-login",
            "Origin": "https://www.zhipin.com",
        }
    )

    try:
        _update_mcp_login_task(task_id, step="qr_preparing", message="正在生成登录二维码...")

        randkey_url = "https://www.zhipin.com/wapi/zppassport/captcha/randkey"
        rand_resp = session.post(randkey_url, timeout=15)
        rand_resp.raise_for_status()
        qr_id = rand_resp.json()["zpData"]["qrId"]

        qr_url = f"https://www.zhipin.com/wapi/zpweixin/qrcode/getqrcode?content={qr_id}"
        qr_resp = session.get(qr_url, timeout=15)
        qr_resp.raise_for_status()

        _update_mcp_login_task(
            task_id,
            step="qr_generated",
            message="二维码已生成，请使用 Boss 直聘 APP 扫码。",
            qr_id=qr_id,
            qr_ready=True,
            qr_bytes=qr_resp.content,
        )

        scan_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/scan?uuid={qr_id}"
        scan_deadline = time.time() + 240
        scanned = False
        while time.time() < scan_deadline:
            try:
                scan_resp = session.get(scan_url, timeout=35)
                if scan_resp.status_code == 200 and scan_resp.json().get("scaned"):
                    scanned = True
                    _update_mcp_login_task(
                        task_id,
                        step="scanned",
                        message="已检测到扫码，正在等待手机端确认登录...",
                    )
                    break
            except requests.exceptions.ReadTimeout:
                pass
            except Exception:
                pass
            time.sleep(1)

        if not scanned:
            _update_mcp_login_task(
                task_id,
                status="failed",
                ok=False,
                step="failed",
                message="等待扫码超时，请重新发起 MCP 登录。",
            )
            return

        confirm_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/scanLogin?qrId={qr_id}&status=1"
        confirm_deadline = time.time() + 240
        confirmed = False
        while time.time() < confirm_deadline:
            try:
                confirm_resp = session.get(confirm_url, timeout=35)
                if confirm_resp.status_code == 200:
                    confirmed = True
                    _update_mcp_login_task(
                        task_id,
                        step="confirmed",
                        message="手机端已确认，正在获取登录 Cookie...",
                    )
                    break
            except requests.exceptions.ReadTimeout:
                pass
            except Exception:
                pass
            time.sleep(1)

        if not confirmed:
            _update_mcp_login_task(
                task_id,
                status="failed",
                ok=False,
                step="failed",
                message="等待手机确认超时，请重新发起 MCP 登录。",
            )
            return

        _update_mcp_login_task(task_id, step="cookie", message="正在交换登录凭证...")
        fp = _generate_boss_fp()
        dispatcher_url = (
            f"https://www.zhipin.com/wapi/zppassport/qrcode/dispatcher?qrId={qr_id}&pk=header-login&fp={fp}"
        )
        cookie_resp = session.get(dispatcher_url, allow_redirects=False, timeout=20)
        cookie_str, bst_value = _parse_set_cookie(cookie_resp.headers.get("Set-Cookie", ""))

        if not cookie_str:
            _update_mcp_login_task(
                task_id,
                status="failed",
                ok=False,
                step="failed",
                message="Cookie 获取失败，请重新发起登录。",
            )
            return

        _update_mcp_login_task(task_id, step="saving", message="已获取 Cookie，正在写入配置...")
        save_ok = save_cookie_to_config(cookie_str, bst_value)
        if not save_ok:
            _update_mcp_login_task(
                task_id,
                status="failed",
                ok=False,
                step="failed",
                message="Cookie 已获取但写入配置失败，请查看日志。",
            )
            return

        _update_mcp_login_task(
            task_id,
            status="done",
            ok=True,
            step="logged_in",
            message="登录成功，Cookie 已保存。",
        )
    except Exception as e:
        _update_mcp_login_task(
            task_id,
            status="failed",
            ok=False,
            step="failed",
            message=f"MCP 登录异常: {e}",
        )


def _add_task_event(task_id: str, text: str, kind: str = "bot") -> None:
    text = str(text or "").strip()
    if not text:
        return
    with TASK_LOCK:
        task = CHAT_TASKS.get(task_id)
        if not task:
            return
        event_id = int(task.get("next_event_id", 1))
        events = task.setdefault("events", [])
        events.append({"id": event_id, "text": text, "kind": kind})
        task["next_event_id"] = event_id + 1
        # 控制内存，避免长任务无限增长。
        if len(events) > 120:
            del events[: len(events) - 120]


def _run_pipeline(
    message: str,
    progress_cb: Callable[[int, str, str], None] | None = None,
    event_cb: Callable[[str, str], None] | None = None,
) -> Dict[str, Any]:
    def step(pct: int, stage: str, text: str) -> None:
        if progress_cb:
            progress_cb(pct, stage, text)

    def emit(text: str, kind: str = "bot") -> None:
        if event_cb:
            event_cb(text, kind)

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
    if intent.intent_provider == "备用AI":
        emit("提示: 意图解析阶段主AI不可用，已自动切换到备用模型（混元）。")
    emit(
        f"执行参数: action={intent.action}, keyword={intent.keyword or '(空)'}, city={intent.city}, pages={intent.pages}"
    )

    if config.ai_api_key:
        step(8, "ai.intent.done", "AI 意图解析完成，正在提取你的个人经历信息...")
    else:
        step(8, "rule.intent.done", "规则意图解析完成，正在提取你的个人经历信息...")
    user_profile = _extract_user_profile(message)
    if intent.personal_strengths_summary:
        user_profile["personal_strengths_summary"] = intent.personal_strengths_summary
        strengths = user_profile.setdefault("strengths", [])
        if intent.personal_strengths_summary not in strengths and len(strengths) < 10:
            strengths.insert(0, intent.personal_strengths_summary)
    step(12, "profile", f"已提取个人信息: {_profile_summary_text(user_profile)}")
    emit(f"个性化信息识别: {_profile_summary_text(user_profile)}")
    if intent.personal_strengths_summary:
        emit(f"AI优势总结: {intent.personal_strengths_summary}")

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
        emit(f"抓取进度: {done_pages}/{total_pages} 页，已获取 {job_count} 条职位。")

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

    scrape_meta = scraper.get_last_run_meta()
    risk_detected = bool(scrape_meta.get("risk_blocked") or scrape_meta.get("entered_browser_mode"))

    if not jobs:
        fail_message = "没有抓取到有效职位数据。请检查关键词、城市或登录状态后重试。"
        if risk_detected:
            fail_message = "没有抓取到有效职位数据，且检测到疑似被风控。系统将进入第二轮重试。"
        return {
            "ok": False,
            "message": fail_message,
            "risk_control_detected": risk_detected,
            "should_retry": risk_detected,
            "scrape_meta": scrape_meta,
        }

    if risk_detected:
        emit(
            "提示: 已检测到被风控，浏览器模式可能跳转空白页。系统将使用第一轮已抓取的数据继续后续分析，不再进入第二轮。"
        )

    step(58, "save-data", "抓取完成，正在保存原始数据...")
    data_path = scraper.save_jobs(jobs)
    emit(f"原始数据已保存: {os.path.basename(data_path)}")

    data_destroyed = False
    result_payload: Dict[str, Any] | None = None
    try:
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
        if getattr(analyzer, "ai_provider_used", "") == "备用AI":
            emit("提示: 深度分析阶段主AI不可用，已自动切换到备用模型（混元）。")

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
        emit(f"新报告已生成: {latest_report}，可在报告中心查看。")

        result_payload = {
            "ok": True,
            "message": summary,
            "intent": {
                "action": intent.action,
                "keyword": intent.keyword,
                "city": intent.city,
                "pages": intent.pages,
                "personal_strengths_summary": intent.personal_strengths_summary,
                "intent_provider": intent.intent_provider,
            },
            "jobs_count": len(jobs),
            "risk_control_detected": risk_detected,
            "scrape_meta": scrape_meta,
            "user_profile": user_profile,
            "user_profile_summary": _profile_summary_text(user_profile),
            "data_file": os.path.basename(data_path),
            "data_destroyed": data_destroyed,
            "report_file": latest_report,
        }
    finally:
        try:
            if data_path and os.path.exists(data_path):
                os.remove(data_path)
                data_destroyed = True
                step(100, "cleanup.data", "任务结束，已销毁本次抓取的原始数据文件。")
                emit(f"原始数据已销毁: {os.path.basename(data_path)}")
        except Exception as cleanup_err:
            emit(f"原始数据销毁失败(不影响报告): {cleanup_err}", kind="error")

    if result_payload is not None:
        result_payload["data_destroyed"] = data_destroyed
        return result_payload

    return {
        "ok": False,
        "message": "任务未生成结果",
        "risk_control_detected": risk_detected,
        "scrape_meta": scrape_meta,
    }


def _run_pipeline_task(task_id: str, message: str) -> None:
    def progress_cb(pct: int, stage: str, text: str) -> None:
        _update_task(task_id, progress=pct, stage=stage, message=text)

    def event_cb(text: str, kind: str = "bot") -> None:
        _add_task_event(task_id, text, kind=kind)

    try:
        result = _run_pipeline(message, progress_cb=progress_cb, event_cb=event_cb)

        should_retry = not result.get("ok") and bool(result.get("should_retry"))
        if should_retry:
            warning = "提示: 检测到首次抓取疑似触发风控，系统将自动按原始输入完整重跑一次流程，因此整体耗时会更长。"
            _add_task_event(task_id, warning, kind="bot")
            _update_task(
                task_id,
                progress=5,
                stage="retry.wind-control",
                message="检测到首次抓取疑似触发风控，系统将按你的原始输入完整重跑一次流程。由于风控原因，本次总耗时会更长，请耐心等待。",
            )
            retry_result = _run_pipeline(message, progress_cb=progress_cb, event_cb=event_cb)
            if retry_result.get("ok"):
                retry_result["retried_due_to_wind_control"] = True
                result = retry_result
            else:
                retry_result["retried_due_to_wind_control"] = True
                retry_result["message"] = (
                    f"{retry_result.get('message', '任务失败')}（已因风控自动重试一次完整流程）"
                )
                result = retry_result

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
        _add_task_event(task_id, f"执行异常: {e}", kind="error")
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


@app.post("/api/boss/mcp-login/start")
def api_boss_mcp_login_start():
    cfg = Config.load()
    if cfg.cookie:
        return jsonify({
            "ok": True,
            "already_logged_in": True,
            "message": "您已登录，进入首页。",
        })

    task_id = _new_mcp_login_task()
    worker = threading.Thread(target=_run_mcp_login_task, args=(task_id,), daemon=True)
    worker.start()

    return jsonify(
        {
            "ok": True,
            "already_logged_in": False,
            "task_id": task_id,
            "qr_url": f"/api/boss/mcp-login/qr/{task_id}",
            "message": "MCP 登录已启动",
        }
    )


@app.get("/api/boss/mcp-login/task/<task_id>")
def api_boss_mcp_login_task(task_id: str):
    task = _get_mcp_login_task(task_id)
    if not task:
        return jsonify({"ok": False, "message": "登录任务不存在"}), 404
    return jsonify({"ok": True, "task": task})


@app.get("/api/boss/mcp-login/qr/<task_id>")
def api_boss_mcp_login_qr(task_id: str):
    task = _get_mcp_login_task(task_id)
    if not task:
        return Response("登录任务不存在", status=404, mimetype="text/plain; charset=utf-8")

    qr_bytes = _get_mcp_qr_bytes(task_id)
    if qr_bytes:
        return Response(qr_bytes, mimetype="image/png")

    html = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="refresh" content="1" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MCP 登录二维码</title>
  <style>
    body { margin: 0; background: #091a2b; color: #d7f2ff; font-family: sans-serif; display: grid; place-items: center; height: 100vh; }
    .box { text-align: center; padding: 16px 20px; border: 1px solid #24506f; border-radius: 12px; }
  </style>
</head>
<body>
  <div class="box">二维码生成中，请稍候...</div>
</body>
</html>
"""
    return Response(html, mimetype="text/html; charset=utf-8")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
