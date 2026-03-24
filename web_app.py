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
import shutil
import time
import threading
import uuid
import base64
import sqlite3
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

import requests
from flask import Flask, jsonify, render_template, request, send_file, Response, stream_with_context, session

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Random import get_random_bytes

from src.analyzer import JobAnalyzer
from src.career_job_store import schedule_upsert_jobs_to_sqlite
from src.career_planning.ai.ai_planner import generate_ai_matching_and_paths
from src.career_planning.data.data_loader import load_jobs_dataframe
from src.career_planning.dialogue.dialogue_manager import (
    build_final_student_text,
    default_state,
    next_dialogue_turn,
)
from src.career_planning.ai.llm_client import LLMClient as CareerLLMClient
from src.career_planning.matching.matcher import match_jobs
from src.career_planning.matching.profiles import (
    build_job_profiles,
    build_related_edges,
    build_transition_graph,
    build_vertical_graph,
)
from src.career_planning.reports.report_generator import (
    export_report as export_career_report,
    generate_report_markdown,
    stream_report_markdown,
)
from src.career_planning.resume.resume_parser import parse_resume_file
from src.config import Config
from src.interview_module import (
    build_interview_feedback,
    build_interview_questions,
    evaluate_answer_completeness,
)
from src.models import CITY_CODES, SearchQuery
from src.report import ReportGenerator
from src.scraper import BossZhipinScraper
from src.boss_zp.cookie_utils import save_cookie_to_config

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, template_folder="template", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("CAREERAI_SECRET_KEY", "careerai-dev-secret-change-me")

TASK_LOCK = threading.Lock()
CHAT_TASKS: Dict[str, Dict[str, Any]] = {}
MCP_LOGIN_LOCK = threading.Lock()
MCP_LOGIN_TASKS: Dict[str, Dict[str, Any]] = {}
INTERVIEW_LOCK = threading.Lock()
INTERVIEW_SESSIONS: Dict[str, Dict[str, Any]] = {}
AUTH_LOCK = threading.Lock()


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


def _users_db_path() -> Path:
    cfg = Config.load()
    data_dir = BASE_DIR / cfg.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "users.db"


def _ensure_user_table() -> None:
    db_path = _users_db_path()
    with AUTH_LOCK:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def _normalize_username(username: str) -> str:
    return re.sub(r"\s+", "", str(username or "").strip().lower())


def _hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, 120_000)
    return digest.hex()


def _create_user(username: str, password: str) -> tuple[bool, str]:
    name = _normalize_username(username)
    if not re.fullmatch(r"[a-z0-9_]{3,32}", name):
        return False, "用户名仅支持 3-32 位字母、数字、下划线。"
    if len(str(password or "")) < 6:
        return False, "密码长度至少 6 位。"

    _ensure_user_table()
    db_path = _users_db_path()

    with AUTH_LOCK:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute("SELECT id FROM users WHERE username = ?", (name,))
            if cur.fetchone():
                return False, "账号已存在，请更换用户名。"

            salt_hex = secrets.token_hex(16)
            password_hash = _hash_password(password, salt_hex)
            conn.execute(
                "INSERT INTO users(username, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, salt_hex, password_hash, int(time.time())),
            )
            conn.commit()
            return True, "注册成功"
        finally:
            conn.close()


def _verify_user(username: str, password: str) -> Dict[str, Any] | None:
    name = _normalize_username(username)
    _ensure_user_table()
    db_path = _users_db_path()

    with AUTH_LOCK:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(
                "SELECT id, username, password_salt, password_hash FROM users WHERE username = ?",
                (name,),
            )
            row = cur.fetchone()
        finally:
            conn.close()

    if not row:
        return None

    user_id, username_db, salt_hex, hash_hex = row
    calc = _hash_password(password, str(salt_hex))
    if not hmac.compare_digest(calc, str(hash_hex)):
        return None

    return {"id": int(user_id), "username": str(username_db)}


def _current_user() -> Dict[str, Any] | None:
    uid = session.get("user_id")
    uname = session.get("username")
    if not uid or not uname:
        return None
    return {"id": int(uid), "username": str(uname)}


def _user_dir_token(user: Dict[str, Any]) -> str:
    seed = f"uid:{int(user.get('id') or 0)}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _get_user_output_dir(user: Dict[str, Any] | None = None) -> Path:
    cfg = Config.load()
    root = BASE_DIR / cfg.output_dir / "users"
    root.mkdir(parents=True, exist_ok=True)
    u = user or _current_user()
    if not u:
        return root / "_guest"
    token = _user_dir_token(u)
    user_dir = root / token
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _require_login() -> tuple[Dict[str, Any] | None, Any | None]:
    user = _current_user()
    if not user:
        return None, (jsonify({"ok": False, "message": "请先登录账号。"}), 401)
    return user, None


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


def _collect_report_files(user: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    output_dir = _get_user_output_dir(user)
    output_dir.mkdir(parents=True, exist_ok=True)

    items: List[Dict[str, Any]] = []
    for file_path in output_dir.glob("*"):
        if not file_path.is_file():
            continue
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


def _get_career_data_dir() -> Path:
    cfg = Config.load()
    return BASE_DIR / cfg.data_dir


def _get_career_output_dir() -> Path:
    return _get_user_output_dir()


def _build_career_llm_client() -> CareerLLMClient:
    cfg = Config.load()

    api_key = str(cfg.ai_api_key or "").strip()
    base_url = str(cfg.ai_base_url or "").strip()
    model = str(cfg.ai_model or "").strip()

    if not api_key and cfg.backup_ai_api_key:
        api_key = str(cfg.backup_ai_api_key or "").strip()
        base_url = str(cfg.backup_ai_base_url or "").strip()
        model = str(cfg.backup_ai_model or "").strip()

    return CareerLLMClient(api_key=api_key, base_url=base_url, model=model)


def _career_recommend_jobs_for_dialogue(student_text: str) -> list[str]:
    text = str(student_text or "").strip()
    if not text:
        return []

    try:
        jobs_df, _ = load_jobs_dataframe(_get_career_data_dir())
        job_profiles = build_job_profiles(jobs_df)
        llm = _build_career_llm_client()
        from src.career_planning.matching.student_profile import build_student_profile

        student_profile = build_student_profile(text, llm=llm)
        ai_bundle = generate_ai_matching_and_paths(
            student_profile=student_profile,
            job_profiles=job_profiles,
            llm_client=llm,
            top_k=8,
        )
        matches = ai_bundle.get("matches") or match_jobs(student_profile, job_profiles, top_k=8)
        return [m.get("job_title", "") for m in matches if m.get("job_title")]
    except Exception:
        return []


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


def _persist_career_jobs_dataset(source_path: str) -> str:
    source = Path(str(source_path or "")).resolve()
    if not source.exists() or not source.is_file():
        return ""

    cfg = Config.load()
    data_dir = BASE_DIR / cfg.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "career_jobs_latest.json"
    shutil.copyfile(source, target)
    return str(target)


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
            "owner_user_id": int(session.get("user_id") or 0),
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
    user: Dict[str, Any] | None = None,
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
    user_output_dir = _get_user_output_dir(user)
    config.output_dir = str(user_output_dir)
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
    report_snapshot = {x["name"] for x in _collect_report_files(user)}

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

    try:
        cfg = Config.load()
        data_dir = BASE_DIR / cfg.data_dir
        schedule_upsert_jobs_to_sqlite([job.to_dict() for job in jobs], data_dir)
        emit("后台任务已启动: 爬取职位将与 SQLite 历史数据比对去重后入库，不影响当前前台流程。")
    except Exception as store_err:
        emit(f"后台SQLite入库启动失败(不影响当前流程): {store_err}", kind="error")

    career_data_path = ""
    try:
        career_data_path = _persist_career_jobs_dataset(data_path)
        if career_data_path:
            emit(f"职业规划数据已更新: {os.path.basename(career_data_path)}")
    except Exception as copy_err:
        emit(f"职业规划数据同步失败(不影响主流程): {copy_err}", kind="error")

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

        report_after = _collect_report_files(user)
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
            "career_data_file": os.path.basename(career_data_path) if career_data_path else "",
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

    owner: Dict[str, Any] | None = None
    task = _get_task(task_id)
    owner_uid = int((task or {}).get("owner_user_id") or 0)
    if owner_uid:
        owner = {"id": owner_uid, "username": ""}

    try:
        result = _run_pipeline(message, user=owner, progress_cb=progress_cb, event_cb=event_cb)

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
            retry_result = _run_pipeline(message, user=owner, progress_cb=progress_cb, event_cb=event_cb)
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
    if not _current_user():
        return render_template("login.html")
    return render_template("index.html")


@app.get("/login")
def login_page():
    if _current_user():
        return render_template("index.html")
    return render_template("login.html")


@app.post("/api/auth/register")
def api_auth_register():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    ok, message = _create_user(username, password)
    if not ok:
        return jsonify({"ok": False, "message": message}), 400
    return jsonify({"ok": True, "message": message})


@app.post("/api/auth/login")
def api_auth_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    user = _verify_user(username, password)
    if not user:
        return jsonify({"ok": False, "message": "用户名或密码错误。"}), 400

    session["user_id"] = int(user["id"])
    session["username"] = str(user["username"])
    return jsonify({"ok": True, "message": "登录成功", "user": user})


@app.post("/api/auth/logout")
def api_auth_logout():
    session.pop("user_id", None)
    session.pop("username", None)
    return jsonify({"ok": True, "message": "已退出登录"})


@app.get("/api/auth/me")
def api_auth_me():
    user = _current_user()
    if not user:
        return jsonify({"ok": True, "logged_in": False})
    return jsonify({"ok": True, "logged_in": True, "user": user})


@app.get("/api/status")
def api_status():
    cfg = Config.load()
    user = _current_user()
    return jsonify(
        {
            "ok": True,
            "logged_in": bool(user),
            "username": (user or {}).get("username", ""),
            "has_cookie": bool(cfg.cookie),
            "ai_configured": bool(cfg.ai_api_key),
            "ai_model": cfg.ai_model,
        }
    )


@app.get("/api/reports")
def api_reports():
    user, err = _require_login()
    if err:
        return err
    return jsonify({"ok": True, "reports": _collect_report_files(user)})


@app.get("/api/reports/<path:report_name>")
def api_report_content(report_name: str):
    user, err = _require_login()
    if err:
        return err

    output_dir = _get_user_output_dir(user).resolve()
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
    user, err = _require_login()
    if err:
        return err

    output_dir = _get_user_output_dir(user).resolve()
    target = (output_dir / report_name).resolve()

    if output_dir not in target.parents or not target.exists():
        return jsonify({"ok": False, "message": "报告不存在"}), 404

    return send_file(target)


@app.post("/api/chat")
def api_chat():
    user, err = _require_login()
    if err:
        return err

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
    user, err = _require_login()
    if err:
        return err

    task = _get_task(task_id)
    if not task:
        return jsonify({"ok": False, "message": "任务不存在"}), 404
    if int(task.get("owner_user_id") or 0) != int(user.get("id") or 0):
        return jsonify({"ok": False, "message": "无权访问该任务"}), 403
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


@app.get("/api/career/health")
def api_career_health():
    _, err = _require_login()
    if err:
        return err

    llm = _build_career_llm_client()
    return jsonify(
        {
            "ok": True,
            "time": int(time.time()),
            "llm_enabled": llm.enabled,
            "data_dir": str(_get_career_data_dir().name),
        }
    )


@app.post("/api/career/analyze")
def api_career_analyze():
    _, err = _require_login()
    if err:
        return err

    print("[DEBUG] 进入 /api/career/analyze")
    try:
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        student_text = str(payload.get("student_text", "")).strip()
        print(f"[DEBUG] 收到 student_text 长度: {len(student_text)}")
        include_report = bool(payload.get("include_report", False))

        if not student_text:
            return jsonify({"ok": False, "error": "请先输入简历或自我描述文本。"}), 400

        try:
            jobs_df, dataset_path = load_jobs_dataframe(_get_career_data_dir())
        except Exception as exc:
            return jsonify({"ok": False, "error": f"读取岗位数据失败: {exc}"}), 500

        llm = _build_career_llm_client()
        from src.career_planning.matching.student_profile import build_student_profile

        job_profiles = build_job_profiles(jobs_df)
        relation_edges = build_related_edges(job_profiles)

        student_profile = build_student_profile(student_text, llm=llm)
        ai_bundle = generate_ai_matching_and_paths(
            student_profile=student_profile,
            job_profiles=job_profiles,
            llm_client=llm,
            top_k=8,
        )

        matches = ai_bundle.get("matches") or match_jobs(student_profile, job_profiles, top_k=8)
        vertical_graph = ai_bundle.get("vertical_graph") or build_vertical_graph(job_profiles)
        transition_graph = ai_bundle.get("transition_graph") or build_transition_graph()

        report_md = ""
        if include_report:
            report_md = generate_report_markdown(
                student_profile=student_profile,
                matches=matches,
                vertical_graph=vertical_graph,
                transition_graph=transition_graph,
                llm_client=llm,
            )

        return jsonify(
            {
                "ok": True,
                "dataset": {
                    "path": dataset_path.name,
                    "job_count": int(len(jobs_df)),
                    "unique_roles": int(len(job_profiles)),
                    "title_categories": int(jobs_df["job_title"].nunique()),
                },
                "job_profiles": job_profiles,
                "vertical_graph": vertical_graph,
                "transition_graph": transition_graph,
                "relation_edges": relation_edges,
                "student_profile": student_profile,
                "matches": matches,
                "report_markdown": report_md,
                "report_ready": bool(report_md),
                "metrics": {
                    "required_job_profiles": len(job_profiles) >= 10,
                    "required_transition_paths": len(transition_graph) >= 5
                    and all(len(x.get("transitions", [])) >= 2 for x in transition_graph),
                    "matching_dimensions": [
                        "foundation_requirements",
                        "professional_skills",
                        "professional_quality",
                        "development_potential",
                    ],
                },
            }
        )
    except Exception as e:
        import traceback
        print("[ERROR] analyze 崩溃:", str(e))
        print(traceback.format_exc())  # ← 加这一行，打印完整栈
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/career/report")
def api_career_report():
    _, err = _require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    student_profile = payload.get("student_profile") or {}
    matches = payload.get("matches") or []
    vertical_graph = payload.get("vertical_graph") or []
    transition_graph = payload.get("transition_graph") or []

    if not student_profile or not matches:
        return jsonify({"ok": False, "error": "报告生成缺少必要的分析结果。"}), 400

    llm = _build_career_llm_client()
    report_md = generate_report_markdown(
        student_profile=student_profile,
        matches=matches,
        vertical_graph=vertical_graph,
        transition_graph=transition_graph,
        llm_client=llm,
    )
    return jsonify({"ok": True, "report_markdown": report_md})


@app.post("/api/career/report/stream")
def api_career_report_stream():
    _, err = _require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    student_profile = payload.get("student_profile") or {}
    matches = payload.get("matches") or []
    vertical_graph = payload.get("vertical_graph") or []
    transition_graph = payload.get("transition_graph") or []
    auto_export = bool(payload.get("auto_export", False))
    report_name = str(payload.get("report_name", "")).strip()

    if not student_profile or not matches:
        def error_stream():
            # Send an SSE prelude to reduce buffering in some proxies/browsers.
            yield f": {' ' * 2048}\n\n"
            err_event = {
                "type": "error",
                "message": "报告流式输出缺少必要的分析结果。请先完成分析并确保 student_profile 与 matches 非空。",
            }
            yield f"data: {json.dumps(err_event, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'mode': 'error', 'final': True}, ensure_ascii=False)}\n\n"

        return Response(
            stream_with_context(error_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    llm = _build_career_llm_client()

    def event_stream():
        assembled_parts: List[str] = []
        try:
            # Send an SSE prelude to reduce buffering in some proxies/browsers.
            yield f": {' ' * 2048}\n\n"
            yield f"data: {json.dumps({'type': 'stage', 'message': '已建立流式通道，开始连续输出'}, ensure_ascii=False)}\n\n"
            for event in stream_report_markdown(
                student_profile=student_profile,
                matches=matches,
                vertical_graph=vertical_graph,
                transition_graph=transition_graph,
                llm_client=llm,
            ):
                if str(event.get("type", "")) == "chunk":
                    assembled_parts.append(str(event.get("content", "")))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            if auto_export:
                markdown_text = "".join(assembled_parts).strip()
                if markdown_text:
                    stem = report_name or f"career_plan_{int(time.time() * 1000)}"
                    try:
                        files = export_career_report(markdown_text, _get_career_output_dir(), stem)
                        default_file = files.get("pdf") or ""
                        if default_file:
                            saved_event = {
                                "type": "saved",
                                "files": files,
                                "default_file": default_file,
                            }
                            yield f"data: {json.dumps(saved_event, ensure_ascii=False)}\n\n"
                        else:
                            warn_event = {
                                "type": "warn",
                                "message": f"报告文本已生成，但 PDF 导出失败: {files.get('pdf_error', '未知错误')}",
                            }
                            yield f"data: {json.dumps(warn_event, ensure_ascii=False)}\n\n"
                    except Exception as exc:
                        warn_event = {
                            "type": "warn",
                            "message": f"已生成报告内容，但自动保存失败: {exc}",
                        }
                        yield f"data: {json.dumps(warn_event, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'mode': 'stream', 'final': True}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            err = {"type": "error", "message": f"流式生成失败: {exc}"}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/career/export")
def api_career_export():
    _, err = _require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    markdown_text = str(payload.get("report_markdown", "")).strip()
    report_name = str(payload.get("report_name", "career_report")).strip()

    if not markdown_text:
        return jsonify({"ok": False, "error": "没有可导出的报告内容。"}), 400

    files = export_career_report(markdown_text, _get_career_output_dir(), report_name)
    default_file = files.get("pdf") or ""
    warning = files.get("pdf_error", "")
    if not default_file:
        return jsonify({"ok": False, "error": warning or "PDF 导出失败"}), 500
    return jsonify({"ok": True, "files": files, "default_file": default_file, "warning": warning})


@app.post("/api/career/resume/parse")
def api_career_resume_parse():
    _, err = _require_login()
    if err:
        return err

    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "请先选择要上传的简历文件。"}), 400

    filename = str(file.filename or "").strip()
    if not filename:
        return jsonify({"ok": False, "error": "无效的文件名。"}), 400

    raw = file.read()
    if not raw:
        return jsonify({"ok": False, "error": "上传文件为空。"}), 400
    if len(raw) > 8 * 1024 * 1024:
        return jsonify({"ok": False, "error": "文件过大，请上传 8MB 以内的简历文件。"}), 400

    try:
        text = parse_resume_file(filename, raw)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"简历解析失败: {exc}"}), 400

    if not text:
        return jsonify({"ok": False, "error": "未从文件中提取到文本，请检查文件内容。"}), 400

    return jsonify({"ok": True, "filename": filename, "text": text})


@app.post("/api/interview/resume/parse")
def api_interview_resume_parse():
    _, err = _require_login()
    if err:
        return err

    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "请先选择要上传的简历文件。"}), 400

    filename = str(file.filename or "").strip()
    if not filename:
        return jsonify({"ok": False, "error": "无效的文件名。"}), 400

    raw = file.read()
    if not raw:
        return jsonify({"ok": False, "error": "上传文件为空。"}), 400
    if len(raw) > 8 * 1024 * 1024:
        return jsonify({"ok": False, "error": "文件过大，请上传 8MB 以内的简历文件。"}), 400

    try:
        text = parse_resume_file(filename, raw)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"简历解析失败: {exc}"}), 400

    if not text:
        return jsonify({"ok": False, "error": "未从文件中提取到文本，请检查文件内容。"}), 400

    return jsonify({"ok": True, "filename": filename, "text": text})


@app.post("/api/interview/start")
def api_interview_start():
    _, err = _require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    resume_text = str(payload.get("resume_text", "")).strip()
    question_count = max(8, min(15, _safe_int(payload.get("question_count"), 10)))

    if not resume_text:
        return jsonify({"ok": False, "error": "请先上传并解析简历，或直接粘贴简历文本。"}), 400

    llm = _build_career_llm_client()
    target_role, questions = build_interview_questions(
        resume_text=resume_text,
        llm_client=llm,
        target_count=question_count,
    )
    if not questions:
        return jsonify({"ok": False, "error": "未能生成面试问题，请稍后重试。"}), 500

    session_id = uuid.uuid4().hex
    session = {
        "session_id": session_id,
        "created_at": int(time.time()),
        "target_role": target_role,
        "resume_text": resume_text[:12000],
        "questions": questions,
        "current_index": 0,
        "attempts": {},
        "records": [],
        "status": "running",
    }
    with INTERVIEW_LOCK:
        INTERVIEW_SESSIONS[session_id] = session

    current_question = questions[0]
    return jsonify(
        {
            "ok": True,
            "session_id": session_id,
            "target_role": target_role,
            "total_questions": len(questions),
            "deep_questions": sum(1 for q in questions if q.get("is_deep")),
            "current": {
                "index": 1,
                "question_id": current_question.get("id", 1),
                "question": current_question.get("question", ""),
                "sub_questions": current_question.get("sub_questions", []),
                "is_deep": bool(current_question.get("is_deep")),
                "category": current_question.get("category", ""),
            },
        }
    )


@app.post("/api/interview/answer")
def api_interview_answer():
    _, err = _require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    session_id = str(payload.get("session_id", "")).strip()
    answer = str(payload.get("answer", "")).strip()

    if not session_id:
        return jsonify({"ok": False, "error": "缺少 session_id。"}), 400
    if not answer:
        return jsonify({"ok": False, "error": "请输入你的回答后再提交。"}), 400

    with INTERVIEW_LOCK:
        session = INTERVIEW_SESSIONS.get(session_id)
    if not session:
        return jsonify({"ok": False, "error": "面试会话不存在或已过期，请重新开始。"}), 404

    if session.get("status") != "running":
        return jsonify({"ok": False, "error": "该面试会话已结束，请重新开始。"}), 400

    questions = session.get("questions") or []
    current_index = int(session.get("current_index", 0))
    if current_index >= len(questions):
        return jsonify({"ok": False, "error": "当前面试已结束。"}), 400

    current_question = questions[current_index]
    llm = _build_career_llm_client()
    evaluation = evaluate_answer_completeness(llm_client=llm, question=current_question, answer=answer)

    status = str(evaluation.get("status", "incomplete"))
    missing_indices = evaluation.get("missing_sub_questions") if isinstance(evaluation.get("missing_sub_questions"), list) else []
    missing_indices = [int(x) for x in missing_indices if isinstance(x, (int, float))]
    sub_questions = current_question.get("sub_questions") if isinstance(current_question.get("sub_questions"), list) else []
    missing_sub_questions = [sub_questions[i] for i in missing_indices if 0 <= i < len(sub_questions)]

    attempts = session.get("attempts") if isinstance(session.get("attempts"), dict) else {}
    qid = str(current_question.get("id", current_index + 1))
    attempts[qid] = int(attempts.get(qid, 0)) + 1
    session["attempts"] = attempts

    record = {
        "question_id": current_question.get("id", current_index + 1),
        "question": current_question.get("question", ""),
        "sub_questions": sub_questions,
        "is_deep": bool(current_question.get("is_deep")),
        "answer": answer,
        "status": "complete" if status == "complete" else "incomplete",
        "missing_sub_questions": missing_sub_questions,
        "quality_score": int(evaluation.get("quality_score", 0) or 0),
        "comment": str(evaluation.get("comment", "")).strip(),
        "attempt": attempts[qid],
    }

    # 同一题最多允许 2 次补充，防止无限卡住。
    if status != "complete" and attempts[qid] < 3:
        session["records"].append(record)
        with INTERVIEW_LOCK:
            INTERVIEW_SESSIONS[session_id] = session
        return jsonify(
            {
                "ok": True,
                "status": "needs_completion",
                "message": "当前回答未覆盖全部小问题，请先补充后再进入下一题。",
                "evaluation": record,
                "current": {
                    "index": current_index + 1,
                    "question_id": current_question.get("id", current_index + 1),
                    "question": current_question.get("question", ""),
                    "sub_questions": sub_questions,
                    "is_deep": bool(current_question.get("is_deep")),
                    "category": current_question.get("category", ""),
                },
            }
        )

    session["records"].append(record)
    session["current_index"] = current_index + 1

    if session["current_index"] < len(questions):
        next_q = questions[session["current_index"]]
        with INTERVIEW_LOCK:
            INTERVIEW_SESSIONS[session_id] = session
        return jsonify(
            {
                "ok": True,
                "status": "next_question",
                "message": "继续下一题。",
                "evaluation": record,
                "current": {
                    "index": session["current_index"] + 1,
                    "question_id": next_q.get("id", session["current_index"] + 1),
                    "question": next_q.get("question", ""),
                    "sub_questions": next_q.get("sub_questions", []),
                    "is_deep": bool(next_q.get("is_deep")),
                    "category": next_q.get("category", ""),
                },
                "progress": {
                    "answered": session["current_index"],
                    "total": len(questions),
                },
            }
        )

    session["status"] = "done"
    feedback = build_interview_feedback(
        llm_client=llm,
        target_role=str(session.get("target_role", "目标岗位")),
        questions=questions,
        records=session.get("records") or [],
    )
    session["feedback"] = feedback
    with INTERVIEW_LOCK:
        INTERVIEW_SESSIONS[session_id] = session

    return jsonify(
        {
            "ok": True,
            "status": "finished",
            "message": "模拟面试已完成，已生成反馈。",
            "evaluation": record,
            "feedback": feedback,
            "progress": {
                "answered": len(questions),
                "total": len(questions),
            },
        }
    )


@app.post("/api/career/dialogue/start")
def api_career_dialogue_start():
    _, err = _require_login()
    if err:
        return err

    llm = _build_career_llm_client()
    turn = next_dialogue_turn(
        state=default_state(),
        user_message="",
        llm_client=llm,
        recommend_jobs=_career_recommend_jobs_for_dialogue,
    )
    return jsonify({"ok": True, **turn})


@app.post("/api/career/dialogue/turn")
def api_career_dialogue_turn():
    _, err = _require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    state = payload.get("state") or default_state()
    user_message = str(payload.get("user_message", "")).strip()

    if not user_message:
        return jsonify({"ok": False, "error": "请输入本轮回答内容。"}), 400

    llm = _build_career_llm_client()
    turn = next_dialogue_turn(
        state=state,
        user_message=user_message,
        llm_client=llm,
        recommend_jobs=_career_recommend_jobs_for_dialogue,
    )
    return jsonify({"ok": True, **turn, "final_student_text": build_final_student_text(turn["state"])})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
