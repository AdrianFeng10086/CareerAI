"""对话意图解析与个人画像提取。"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List

import requests

from app.utils.common import safe_int
from app.utils.json_extract import extract_json_block
from app.utils.llm_client import build_chat_completions_url
from src.config import Config
from src.models import CITY_CODES


@dataclass
class ChatIntent:
    """对话指令意图。"""

    action: str
    keyword: str
    city: str
    pages: int
    personal_strengths_summary: str = ""
    intent_provider: str = ""


def _ask_llm_for_intent(config: Config, message: str) -> ChatIntent | None:
    """在配置了 AI Key 时，尝试让模型把自然语言转为结构化查询。"""
    if not config.ai_api_key and not config.backup_ai_api_key:
        return None

    providers = [
        {
            "name": "主AI",
            "api_key": config.ai_api_key,
            "base_url": build_chat_completions_url(config.ai_base_url),
            "model": config.ai_model,
            "enable_enhancement": False,
        }
    ]
    if config.backup_ai_api_key:
        providers.append(
            {
                "name": "备用AI",
                "api_key": config.backup_ai_api_key,
                "base_url": build_chat_completions_url(config.backup_ai_base_url),
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
        from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout

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
                    parsed = extract_json_block(content)
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
        pages = max(1, min(5, safe_int(parsed.get("pages"), 2)))
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
        pages = max(1, min(5, safe_int(page_match.group(1), 2)))

    keyword = ""
    keyword_match = re.search(r"(?:搜索|查找|分析|查询|找)\s*([一-龥A-Za-z0-9+#\.\-]+)", text)
    if keyword_match:
        keyword = keyword_match.group(1).strip()

    if not keyword and action == "search":
        cleaned = text
        for token in ["请", "帮我", "一下", "岗位", "职位", "工作", "搜索", "查找", "分析", "查询", "找"]:
            cleaned = cleaned.replace(token, "")
        cleaned = cleaned.strip(" ，,。.!！?？")
        keyword = cleaned[:30] if cleaned else "Python开发"

    return ChatIntent(action=action, keyword=keyword, city=city, pages=pages, intent_provider="规则解析")


def parse_intent(config: Config, message: str) -> ChatIntent:
    intent = _ask_llm_for_intent(config, message)
    if intent is not None:
        return intent
    return _fallback_intent(message)


def extract_user_profile(message: str) -> Dict[str, Any]:
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
        r"(?:找|应聘|求职|投递|冲|面向)\s*(?:一个|一份|岗位|职位)?\s*([一-龥A-Za-z0-9+\-#/]{2,30})\s*(?:岗|岗位|职位)?",
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
        fallback_notes = [x.strip() for x in re.split(r"[\n]+", text) if x.strip()][:3]
        profile["personal_notes"] = [x[:120] for x in fallback_notes]

    compact_profile = {k: v for k, v in profile.items() if v}
    return compact_profile


def profile_summary_text(profile: Dict[str, Any]) -> str:
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


def append_query_candidate(candidates: List[str], value: Any) -> None:
    query = re.sub(r"\s+", " ", str(value or "").strip())
    query = query.strip("，,。；;：:|/()[]{}（）")
    if not query:
        return

    if query in {"未填", "未填写", "未明确", "暂无", "未知", "没有"}:
        return

    if len(query) > 30:
        query = query[:30]

    if query not in candidates:
        candidates.append(query)


def extract_dialogue_rag_queries(student_text: str, max_queries: int = 6) -> List[str]:
    text = str(student_text or "").strip()
    if not text:
        return []

    candidates: List[str] = []
    profile = extract_user_profile(text)

    append_query_candidate(candidates, profile.get("target_role", ""))
    for item in (profile.get("research_focus", []) or [])[:3]:
        append_query_candidate(candidates, item)
    for item in (profile.get("tech_stack", []) or [])[:4]:
        append_query_candidate(candidates, item)

    for match in re.finditer(r"(?:目标岗位|意向岗位|意向方向|兴趣方向|专业|主修)\s*[:：]\s*([^\n,，。；;]{2,36})", text):
        append_query_candidate(candidates, match.group(1))

    for segment in re.split(r"[\n,，。；;|/]+", text):
        clean = str(segment or "").strip()
        if 2 <= len(clean) <= 24:
            append_query_candidate(candidates, clean)
        if len(candidates) >= max_queries:
            break

    if not candidates:
        append_query_candidate(candidates, text[:30])

    return candidates[: max(1, int(max_queries))]


def extract_job_titles_from_rag_contexts(contexts: List[str], limit: int = 8) -> List[str]:
    title_pattern = re.compile(r"^\[岗位\d+\]\s*(.+)$")
    title_hits: Dict[str, int] = {}
    first_seen: Dict[str, int] = {}
    sequence = 0

    for ctx in contexts:
        for line in str(ctx or "").splitlines():
            match = title_pattern.match(line.strip())
            if not match:
                continue

            title = re.sub(r"\s+", " ", match.group(1)).strip()
            if not title:
                continue

            title_hits[title] = title_hits.get(title, 0) + 1
            if title not in first_seen:
                first_seen[title] = sequence
                sequence += 1

    ranked = sorted(title_hits.items(), key=lambda item: (-item[1], first_seen[item[0]]))
    return [title for title, _ in ranked[: max(1, int(limit))]]
