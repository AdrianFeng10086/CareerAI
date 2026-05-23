from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from src.career_planning.ai.llm_client import LLMClient


def _extract_json_block(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    if "```" in raw:
        candidate = re.sub(r"^```(?:json)?\\s*", "", raw, flags=re.IGNORECASE)
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


def _extract_target_role(resume_text: str) -> str:
    text = str(resume_text or "").strip()
    if not text:
        return "目标岗位"

    patterns = [
        r"(?:求职意向|应聘岗位|目标岗位|意向岗位)[:：\s]*([^\n，,。]{2,30})",
        r"(?:申请|应聘)\s*([^\n，,。]{2,30})",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            role = m.group(1).strip()
            role = re.sub(r"[。；;]+$", "", role)
            if role:
                return role[:30]

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines[:20]:
        if any(k in ln for k in ["工程师", "产品", "运营", "算法", "分析", "设计", "测试", "前端", "后端"]):
            return ln[:30]

    return "目标岗位"


def _fallback_questions(target_role: str, count: int) -> List[Dict[str, Any]]:
    bank = [
        {
            "question": f"请先做一个简短自我介绍，并说明你为什么选择{target_role}这个方向？",
            "sub_questions": ["你的核心经历是什么", "为什么选择这个岗位"],
            "is_deep": False,
            "category": "动机与匹配",
        },
        {
            "question": "你最近一个最能体现能力的项目是什么？请完整介绍。",
            "sub_questions": ["项目背景与目标", "你的职责", "关键结果与指标"],
            "is_deep": False,
            "category": "项目经历",
        },
        {
            "question": f"请结合{target_role}岗位要求，说说你最有优势的三项能力。",
            "sub_questions": ["能力点1及证据", "能力点2及证据", "能力点3及证据"],
            "is_deep": False,
            "category": "能力匹配",
        },
        {
            "question": "你遇到过最棘手的问题是什么？你是如何拆解并推进解决的？",
            "sub_questions": ["问题现象", "分析过程", "最终方案", "复盘收获"],
            "is_deep": True,
            "category": "深度问题",
        },
        {
            "question": "如果加入团队，你会如何快速进入状态并在30天内产出价值？",
            "sub_questions": ["熟悉业务的方法", "30天计划", "可衡量结果"],
            "is_deep": False,
            "category": "落地执行",
        },
        {
            "question": "你和跨部门合作时遇到意见冲突通常怎么处理？",
            "sub_questions": ["冲突场景", "沟通方式", "达成一致结果"],
            "is_deep": False,
            "category": "协作沟通",
        },
        {
            "question": "你目前最明显的能力短板是什么？准备如何补齐？",
            "sub_questions": ["短板描述", "补齐路径", "时间节点"],
            "is_deep": False,
            "category": "自我认知",
        },
        {
            "question": "请分享一次你通过数据或证据推动决策的经历。",
            "sub_questions": ["使用了哪些数据", "如何说服他人", "最终效果"],
            "is_deep": False,
            "category": "数据能力",
        },
        {
            "question": f"假设你入职后发现{target_role}岗位目标不清晰，你会如何厘清并推进？",
            "sub_questions": ["如何定义目标", "如何对齐相关方", "如何验证执行效果"],
            "is_deep": True,
            "category": "深度问题",
        },
        {
            "question": "你未来1-2年的职业规划是什么？为什么这样规划？",
            "sub_questions": ["目标岗位层级", "关键里程碑", "与你当前能力的关系"],
            "is_deep": False,
            "category": "发展规划",
        },
    ]

    selected = bank[: max(8, min(15, count))]
    for idx, q in enumerate(selected, start=1):
        q["id"] = idx
    return selected


def build_interview_questions(resume_text: str, llm_client: LLMClient, target_count: int = 10) -> Tuple[str, List[Dict[str, Any]]]:
    role = _extract_target_role(resume_text)
    count = max(8, min(15, int(target_count or 10)))

    if not llm_client.enabled:
        return role, _fallback_questions(role, count)

    system_prompt = (
        "你是一位严谨的中文技术面试官。"
        "你的任务是基于候选人简历，生成结构化模拟面试题。"
        "你必须只输出 JSON，不要解释。"
    )
    user_prompt = (
        "请根据以下简历内容输出 JSON。"
        "JSON schema: {\"target_role\": str, \"questions\": [{\"question\": str, \"sub_questions\": [str], \"is_deep\": bool, \"category\": str}]}。"
        f"要求: 题目数量 {count} 个；总数范围 8-15；其中深度问题 1-2 个。"
        "每个问题允许包含多个小问题，sub_questions 至少 2 条。"
        "问题要贴合简历中的求职岗位。"
        f"简历:\n{resume_text[:6000]}"
    )
    parsed = _extract_json_block(llm_client.generate_text(system_prompt, user_prompt, max_tokens=2600))

    raw_role = str(parsed.get("target_role", "")).strip() or role
    raw_questions = parsed.get("questions") if isinstance(parsed.get("questions"), list) else []
    normalized: List[Dict[str, Any]] = []

    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        if not question:
            continue
        sub = item.get("sub_questions") if isinstance(item.get("sub_questions"), list) else []
        sub_questions = [str(x).strip() for x in sub if str(x).strip()]
        if len(sub_questions) < 2:
            sub_questions = ["请说明关键做法", "请说明结果与复盘"]
        normalized.append(
            {
                "question": question,
                "sub_questions": sub_questions[:4],
                "is_deep": bool(item.get("is_deep", False)),
                "category": str(item.get("category", "综合能力")).strip() or "综合能力",
            }
        )

    if len(normalized) < 8:
        return raw_role, _fallback_questions(raw_role, count)

    normalized = normalized[:15]
    if len(normalized) < count:
        extra = _fallback_questions(raw_role, count)
        for q in extra:
            if len(normalized) >= count:
                break
            normalized.append(
                {
                    "question": q["question"],
                    "sub_questions": q["sub_questions"],
                    "is_deep": q["is_deep"],
                    "category": q["category"],
                }
            )
    else:
        normalized = normalized[:count]

    deep_indices = [idx for idx, q in enumerate(normalized) if q.get("is_deep")]
    if len(deep_indices) == 0:
        normalized[min(3, len(normalized) - 1)]["is_deep"] = True
    elif len(deep_indices) > 2:
        keep = set(deep_indices[:2])
        for idx in deep_indices:
            if idx not in keep:
                normalized[idx]["is_deep"] = False

    for idx, q in enumerate(normalized, start=1):
        q["id"] = idx

    return raw_role, normalized


def _fallback_coverage(sub_questions: List[str], answer: str) -> Tuple[List[int], List[int]]:
    text = str(answer or "").lower()
    covered: List[int] = []
    for i, sq in enumerate(sub_questions):
        tokens = re.findall(r"[a-zA-Z0-9\u4e00-\u9fa5]{2,}", str(sq).lower())
        tokens = [tk for tk in tokens if len(tk) >= 2][:4]
        if not tokens:
            continue
        hit = sum(1 for tk in tokens if tk in text)
        if hit >= max(1, min(2, len(tokens))):
            covered.append(i)

    missing = [i for i in range(len(sub_questions)) if i not in covered]
    return covered, missing


def evaluate_answer_completeness(
    llm_client: LLMClient,
    question: Dict[str, Any],
    answer: str,
) -> Dict[str, Any]:
    sub_questions = question.get("sub_questions") if isinstance(question.get("sub_questions"), list) else []
    sub_questions = [str(x).strip() for x in sub_questions if str(x).strip()]
    answer_text = str(answer or "").strip()

    if not sub_questions:
        sub_questions = ["请补充核心做法", "请补充结果说明"]

    if not answer_text:
        return {
            "status": "incomplete",
            "covered_sub_questions": [],
            "missing_sub_questions": list(range(len(sub_questions))),
            "comment": "回答为空，未覆盖小问题。",
            "quality_score": 0,
        }

    if llm_client.enabled:
        system_prompt = "你是面试评估助手，只输出 JSON。"
        user_prompt = (
            "请判断候选人回答是否完整覆盖该题的所有小问题。"
            "只输出 JSON: {\"covered_sub_questions\": [int], \"missing_sub_questions\": [int], \"status\": \"complete|incomplete\", \"comment\": str, \"quality_score\": int}。"
            "索引从0开始，quality_score范围0-100。"
            f"大问题: {question.get('question', '')}\n"
            f"小问题: {json.dumps(sub_questions, ensure_ascii=False)}\n"
            f"候选人回答: {answer_text[:2500]}"
        )
        parsed = _extract_json_block(llm_client.generate_text(system_prompt, user_prompt, max_tokens=900))
        if parsed:
            covered = parsed.get("covered_sub_questions") if isinstance(parsed.get("covered_sub_questions"), list) else []
            missing = parsed.get("missing_sub_questions") if isinstance(parsed.get("missing_sub_questions"), list) else []
            covered_idx = sorted({int(x) for x in covered if isinstance(x, (int, float)) and 0 <= int(x) < len(sub_questions)})
            missing_idx = sorted({int(x) for x in missing if isinstance(x, (int, float)) and 0 <= int(x) < len(sub_questions)})
            if not missing_idx:
                missing_idx = [i for i in range(len(sub_questions)) if i not in covered_idx]
            status = str(parsed.get("status", "incomplete")).strip().lower()
            if status not in {"complete", "incomplete"}:
                status = "complete" if not missing_idx else "incomplete"
            if not missing_idx:
                status = "complete"
            comment = str(parsed.get("comment", "")).strip() or ("回答完整。" if status == "complete" else "回答存在缺漏。")
            score = int(parsed.get("quality_score", 0) or 0)
            score = max(0, min(100, score))
            return {
                "status": status,
                "covered_sub_questions": covered_idx,
                "missing_sub_questions": missing_idx,
                "comment": comment,
                "quality_score": score,
            }

    covered_idx, missing_idx = _fallback_coverage(sub_questions, answer_text)
    status = "complete" if not missing_idx else "incomplete"
    return {
        "status": status,
        "covered_sub_questions": covered_idx,
        "missing_sub_questions": missing_idx,
        "comment": "回答完整。" if status == "complete" else "回答欠缺，部分小问题未覆盖。",
        "quality_score": 75 if status == "complete" else 45,
    }


def build_interview_feedback(
    llm_client: LLMClient,
    target_role: str,
    questions: List[Dict[str, Any]],
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total = len(questions)
    answered = len(records)
    complete_count = sum(1 for r in records if r.get("status") == "complete")
    incomplete_count = answered - complete_count
    timeout_count = sum(1 for r in records if r.get("timed_out") is True)
    deep_total = sum(1 for q in questions if q.get("is_deep"))
    deep_complete = sum(
        1
        for r in records
        if r.get("is_deep") and r.get("status") == "complete"
    )
    avg_score = int(round(sum(int(r.get("quality_score", 0) or 0) for r in records) / max(1, answered)))

    summary = {
        "target_role": target_role,
        "total_questions": total,
        "answered_questions": answered,
        "complete_answers": complete_count,
        "incomplete_answers": incomplete_count,
        "timeout_questions": timeout_count,
        "deep_questions": deep_total,
        "deep_complete": deep_complete,
        "average_score": avg_score,
    }

    base_gaps = [
        "部分问题回答不完整，存在关键信息遗漏",
        "深度问题可以补充更多数据和复盘细节",
    ]
    if timeout_count > 0:
        base_gaps.insert(
            0,
            f"有 {timeout_count} 题在 5 分钟作答时间内未完成提交，影响整体表现与得分",
        )

    default_feedback = {
        "summary": summary,
        "overall_comment": "面试已完成。建议重点补齐回答中遗漏的小问题，增强结构化表达。",
        "strengths": [
            "能够结合经历进行说明",
            "具备一定岗位匹配意识",
        ],
        "gaps": base_gaps,
        "action_items": [
            "用 STAR 结构重写关键项目回答",
            "每题按“小问题清单”逐项覆盖再作答",
            "对深度题准备1-2个可量化案例",
        ],
    }

    if not llm_client.enabled:
        return default_feedback

    system_prompt = "你是资深中文面试教练，只输出 JSON。"
    user_prompt = (
        "请根据以下模拟面试结果给出反馈。"
        "输出 JSON: {\"overall_comment\": str, \"strengths\": [str], \"gaps\": [str], \"action_items\": [str]}。"
        "每个数组给3条，简洁可执行。"
        "若 timeout_questions 大于 0，请在 gaps 中明确指出超时未答的问题，"
        "并在 action_items 中给出针对作答时间管理的具体建议。"
        f"目标岗位: {target_role}\n"
        f"统计: {json.dumps(summary, ensure_ascii=False)}\n"
        f"逐题记录: {json.dumps(records, ensure_ascii=False)[:7000]}"
    )
    parsed = _extract_json_block(llm_client.generate_text(system_prompt, user_prompt, max_tokens=1500))
    if not parsed:
        return default_feedback

    return {
        "summary": summary,
        "overall_comment": str(parsed.get("overall_comment", "")).strip() or default_feedback["overall_comment"],
        "strengths": [str(x).strip() for x in (parsed.get("strengths") or []) if str(x).strip()][:5]
        or default_feedback["strengths"],
        "gaps": [str(x).strip() for x in (parsed.get("gaps") or []) if str(x).strip()][:5]
        or default_feedback["gaps"],
        "action_items": [str(x).strip() for x in (parsed.get("action_items") or []) if str(x).strip()][:6]
        or default_feedback["action_items"],
    }
