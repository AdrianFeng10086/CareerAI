from __future__ import annotations

import json
from typing import Any, Dict, List

from .llm_client import LLMClient


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _ensure_path(item: Dict[str, Any], title: str) -> Dict[str, Any]:
    path = item.get("path") or []
    if not isinstance(path, list) or len(path) < 2:
        path = [f"初级{title}", title, f"资深{title}", f"{title}主管"]
    return {
        "job_title": title,
        "path": [str(x) for x in path[:6]],
        "description": str(item.get("description") or f"{title} 的典型垂直发展路径。"),
    }


def _ensure_transition(item: Dict[str, Any], title: str) -> Dict[str, Any]:
    transitions = item.get("transitions") or []
    if not isinstance(transitions, list) or len(transitions) < 2:
        transitions = [f"相关{title}", "跨方向发展"]
    return {
        "job_title": title,
        "transitions": [str(x) for x in transitions[:5]],
    }


def _parse_json_obj(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            data = json.loads(raw[start : end + 1])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def generate_ai_matching_and_paths(
    student_profile: Dict[str, Any],
    job_profiles: List[Dict[str, Any]],
    llm_client: LLMClient,
    top_k: int = 8,
) -> Dict[str, Any]:
    if not llm_client or not llm_client.enabled:
        return {}

    # Compress profile fields to reduce prompt size but keep decision signals.
    compact_jobs = []
    for p in job_profiles[:140]:
        compact_jobs.append(
            {
                "job_title": p.get("job_title", ""),
                "core_hard_skills": (p.get("core_hard_skills") or [])[:8],
                "core_soft_skills": (p.get("core_soft_skills") or [])[:6],
                "cert_requirements": (p.get("cert_requirements") or [])[:4],
                "avg_salary_k": p.get("avg_salary_k", 0),
                "top_cities": (p.get("top_cities") or [])[:3],
                "learning_ability": p.get("learning_ability", 0.6),
                "stress_tolerance": p.get("stress_tolerance", 0.6),
                "communication_ability": p.get("communication_ability", 0.6),
                "innovation_ability": p.get("innovation_ability", 0.6),
            }
        )

    system_prompt = (
        "你是资深职业规划顾问与人岗匹配专家。"
        "请基于学生画像与岗位画像，输出严谨JSON，不要输出解释文本。"
    )
    user_prompt = (
        "请返回一个JSON对象，字段必须为:\n"
        "matches: 列表，长度8，元素字段: job_title, score, dimension_scores, advantage_skills, gap_skills\n"
        "dimension_scores字段包含: foundation_requirements, professional_skills, professional_quality, development_potential\n"
        "vertical_graph: 列表，长度8，元素字段: job_title, path(至少4节点), description\n"
        "transition_graph: 列表，长度5，元素字段: job_title, transitions(至少2项)\n"
        "规则:\n"
        "1) 所有分数范围0-100，score保留1位小数。\n"
        "2) score应与4维评分一致，不能随机。\n"
        "3) path和transitions要可执行、有职业逻辑。\n"
        "4) 尽量覆盖不同岗位，不要8个都高度重复。\n"
        f"学生画像: {student_profile}\n"
        f"岗位画像候选: {compact_jobs}\n"
    )

    raw = llm_client.generate_text(system_prompt, user_prompt, max_tokens=2600)
    data = _parse_json_obj(raw)
    if not data:
        return {}

    out_matches: List[Dict[str, Any]] = []
    for m in (data.get("matches") or [])[: max(1, top_k)]:
        title = str(m.get("job_title") or "").strip()
        if not title:
            continue
        dims = m.get("dimension_scores") or {}
        dim_obj = {
            "foundation_requirements": round(max(0.0, min(100.0, _safe_float(dims.get("foundation_requirements"), 0.0))), 1),
            "professional_skills": round(max(0.0, min(100.0, _safe_float(dims.get("professional_skills"), 0.0))), 1),
            "professional_quality": round(max(0.0, min(100.0, _safe_float(dims.get("professional_quality"), 0.0))), 1),
            "development_potential": round(max(0.0, min(100.0, _safe_float(dims.get("development_potential"), 0.0))), 1),
        }
        score = _safe_float(m.get("score"), 0.0)
        if score <= 0:
            score = (
                0.22 * dim_obj["foundation_requirements"]
                + 0.43 * dim_obj["professional_skills"]
                + 0.20 * dim_obj["professional_quality"]
                + 0.15 * dim_obj["development_potential"]
            )

        out_matches.append(
            {
                "job_title": title,
                "score_raw": round(score, 2),
                "score": round(max(0.0, min(100.0, score)), 1),
                "dimension_scores": dim_obj,
                "advantage_skills": [str(x) for x in (m.get("advantage_skills") or [])[:6]],
                "gap_skills": [str(x) for x in (m.get("gap_skills") or [])[:6]],
                "debug_factors": {},
                "weighting": {
                    "foundation_requirements": 0.22,
                    "professional_skills": 0.43,
                    "professional_quality": 0.2,
                    "development_potential": 0.15,
                },
            }
        )

    # Deduplicate and keep top-k by score.
    dedup: Dict[str, Dict[str, Any]] = {}
    for m in out_matches:
        old = dedup.get(m["job_title"])
        if not old or m["score"] > old["score"]:
            dedup[m["job_title"]] = m
    out_matches = sorted(dedup.values(), key=lambda x: x.get("score", 0), reverse=True)[:top_k]

    out_vertical = []
    for item in (data.get("vertical_graph") or [])[:top_k]:
        title = str(item.get("job_title") or "").strip()
        if not title:
            continue
        out_vertical.append(_ensure_path(item, title))

    out_transition = []
    for item in (data.get("transition_graph") or [])[:5]:
        title = str(item.get("job_title") or "").strip()
        if not title:
            continue
        out_transition.append(_ensure_transition(item, title))

    return {
        "matches": out_matches,
        "vertical_graph": out_vertical,
        "transition_graph": out_transition,
    }
