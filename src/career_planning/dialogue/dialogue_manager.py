from __future__ import annotations

from typing import Any, Callable, Dict, List
import re

from ..ai.llm_client import LLMClient
from ..matching.student_profile import build_student_profile


def default_state() -> Dict[str, Any]:
    return {
        "node": "r1_has_resume",
        "step": 1,
        "mode": "targeted",
        "recommended_jobs": [],
        "has_resume": None,
        "resume_text": "",
        "major": "",
        "grade": "",
        "interests": "",
        "target_job": "",
        "target_reason": "",
        "target_range": "",
        "explore_work_type": "",
        "explore_priority": "",
        "communication_self_eval": "",
        "project_details": "",
        "mbti_type": "", 
        "holland_code": "", 
        "holland_scores_text": "",
        "iceberg_notes": "",
        "assessment_answers": {},
        "ready": False,
    }


def build_final_student_text(state: Dict[str, Any]) -> str:
    if state.get("has_resume"):
        stage1 = state.get("resume_text", "")
    else:
        stage1 = "\n".join(
            [
                f"专业: {state.get('major', '')}",
                f"年级: {state.get('grade', '')}",
                f"兴趣方向: {state.get('interests', '')}",
            ]
        )

    return "\n".join(
        [
            stage1,
            f"目标岗位: {state.get('target_job') or '未明确'}",
            f"目标理由: {state.get('target_reason') or '未填写'}",
            f"可接受范围: {state.get('target_range') or '未填写'}",
            f"偏好工作内容: {state.get('explore_work_type') or '未填写'}",
            f"优先考虑条件: {state.get('explore_priority') or '未填写'}",
            f"沟通能力自评: {state.get('communication_self_eval') or '未填写'}",
            f"项目经历细节: {state.get('project_details') or '未填写'}",
            f"MBTI结果: {state.get('mbti_type') or '未填写'}",
            f"霍兰德代码: {state.get('holland_code') or '未填写'}",
            f"霍兰德分数: {state.get('holland_scores_text') or '未填写'}",
            f"能力素质冰山补充: {state.get('iceberg_notes') or '未填写'}",
        ]
    )


def _is_yes(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    if _is_no(t):
        return False
    return bool(re.search(r"^(有|是|要|好|可以|好的|行|想|yes|y|ok)$", t, flags=re.IGNORECASE))


def _is_no(text: str) -> bool:
    return bool(re.search(r"(没有|否|no|n|无)", text, flags=re.IGNORECASE))


def _explicit_skip_tools(text: str) -> bool:
    return bool(re.search(r"(不做|不测|不需要|跳过|先不做|先不测|暂不)", text, flags=re.IGNORECASE))


def _is_no_target(text: str) -> bool:
    return bool(re.search(r"(没有目标|暂无目标|不确定|不知道|没想好|都可以|先看看|还没定|尚未明确)", text, flags=re.IGNORECASE))


def _infer_target_job(text: str, jobs: List[str]) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""

    for j in jobs:
        if raw in j or j in raw:
            return j

    first = re.split(r"[，,。；;、\s]+", raw)[0].strip()
    return first if len(first) >= 2 else raw


def _extract_resume_prefill(text: str, llm_client: LLMClient) -> Dict[str, str]:
    profile = build_student_profile(text, llm=llm_client)
    out = {
        "major": "",
        "grade": "",
        "interests": "",
        "target_job": str(profile.get("employment_intention", "") or "").strip(),
        "target_reason": "",
        "target_range": "",
        "communication_self_eval": "",
        "project_details": "",
        "mbti_type": str(profile.get("mbti_type", "") or "").strip(),
        "holland_code": str(profile.get("holland_code", "") or "").strip(),
        "iceberg_notes": "",
    }

    stage_label = str(profile.get("academic_stage_label", "") or "").strip()
    if stage_label and stage_label != "未识别":
        out["grade"] = stage_label

    major_match = re.search(r"(专业|主修)[:：]?\s*([^\n。；;]{2,30})", text, flags=re.IGNORECASE)
    if major_match:
        out["major"] = major_match.group(2).strip()

    interest_match = re.search(r"(兴趣方向|方向|意向方向)[:：]?\s*([^\n。；;]{2,40})", text, flags=re.IGNORECASE)
    if interest_match:
        out["interests"] = interest_match.group(2).strip()

    project_match = re.search(r"(项目经历|项目经验|项目)[:：]?\s*([^\n]{8,200})", text, flags=re.IGNORECASE)
    if project_match:
        out["project_details"] = project_match.group(2).strip()

    comm_match = re.search(r"(沟通|协作|表达)[^\n。；;]{0,40}(能力|经验)?[^\n。；;]{0,40}", text, flags=re.IGNORECASE)
    if comm_match:
        out["communication_self_eval"] = comm_match.group(0).strip()

    if llm_client and llm_client.enabled:
        system_prompt = "你是简历信息抽取助手，只输出JSON。"
        user_prompt = (
            "请从简历文本中抽取字段并输出JSON，字段固定为: "
            "major, grade, interests, target_job, target_reason, target_range, communication_self_eval, project_details, mbti_type, holland_code, iceberg_notes。"
            "没有就输出空字符串。不要输出额外解释。\n"
            f"文本: {text}"
        )
        data = llm_client.generate_json(system_prompt, user_prompt)
        if isinstance(data, dict):
            for k in out.keys():
                v = str(data.get(k, "") or "").strip()
                if v and not out.get(k):
                    out[k] = v

    return out


def _ask_next_missing_after_resume(st: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    jobs_text = "、".join(st.get("recommended_jobs", [])) if st.get("recommended_jobs") else "暂无明确推荐"

    if not st.get("target_job"):
        st["step"] = 2
        st["node"] = "r2_target"
        q = _friendly_ask(
            llm_client,
            goal="简历已解析，追问缺失目标岗位",
            context={"recommended_jobs": st.get("recommended_jobs", [])},
            fallback=f"我已从简历提取了大部分信息。你最想先尝试哪个岗位？可参考：{jobs_text}。",
        )
        return {"state": st, "assistant_message": q, "step": 2, "ready": False}

    if not st.get("target_reason"):
        st["step"] = 2
        st["node"] = "r2_reason"
        q = _friendly_ask(
            llm_client,
            goal="简历已解析，追问缺失目标理由",
            context={"target_job": st.get("target_job")},
            fallback=f"我先帮你锁定岗位为“{st.get('target_job')}”。你为什么优先这个岗位？",
        )
        return {"state": st, "assistant_message": q, "step": 2, "ready": False}

    if not st.get("target_range"):
        st["step"] = 2
        st["node"] = "r2_range"
        q = _friendly_ask(
            llm_client,
            goal="简历已解析，追问缺失可接受范围",
            context={"target_job": st.get("target_job")},
            fallback="你可接受的范围是怎样的，比如相近岗位、行业或城市？",
        )
        return {"state": st, "assistant_message": q, "step": 2, "ready": False}

    if not st.get("communication_self_eval"):
        st["step"] = 3
        st["node"] = "r3_communication"
        q = _friendly_ask(
            llm_client,
            goal="简历已解析，追问缺失沟通自评",
            context={},
            fallback="最后补一个小信息：你对自己的沟通协作能力怎么评价？",
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": False}

    if not st.get("project_details"):
        st["step"] = 3
        st["node"] = "r3_project"
        q = _friendly_ask(
            llm_client,
            goal="简历已解析，追问缺失项目细节",
            context={},
            fallback="再补一个项目细节就好：你在项目里的角色、产出和结果是什么？",
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": False}

    if not st.get("mbti_type") and not st.get("holland_code") and not st.get("iceberg_notes"):
        st["step"] = 3
        st["node"] = "r3_career_tools"
        q = _friendly_ask(
            llm_client,
            goal="补充职业规划工具信息",
            context={},
            fallback="如果你做过MBTI、霍兰德或能力素质冰山测评，请把结果发我；没有可直接回复“没有”。",
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": False}

    st["step"] = 3
    st["node"] = "ready"
    st["ready"] = True
    q = _friendly_ask(
        llm_client,
        goal="简历信息完整，提示可生成报告",
        context={"target_job": st.get("target_job")},
        fallback="我已经从简历中补齐了主要信息，你可以直接生成完整报告了。",
    )
    return {"state": st, "assistant_message": q, "step": 3, "ready": True}


def _friendly_ask(
    llm_client: LLMClient,
    goal: str,
    context: Dict[str, Any],
    fallback: str,
) -> str:
    if not llm_client or not llm_client.enabled:
        return fallback

    system_prompt = (
        "你是高校职业规划对话助手。"
        "语气要温和、鼓励、像学长学姐，不要像HR审问。"
        "每次只提出一个清晰问题，20-45字，避免命令口吻。"
    )
    user_prompt = (
        "请根据目标与上下文，输出给学生的一句话（仅一句，不要编号，不要解释规则）。\n"
        f"目标: {goal}\n"
        f"上下文: {context}\n"
        f"兜底参考: {fallback}"
    )
    text = llm_client.generate_text(system_prompt, user_prompt, max_tokens=120)
    return text.strip() if text else fallback


def _infer_holland_from_text(text: str) -> str:
    t = str(text or "")
    score = {"R": 0, "I": 0, "A": 0, "S": 0, "E": 0, "C": 0}
    lexicon = {
        "R": ["动手", "工程", "硬件", "机械", "实操", "实验"],
        "I": ["研究", "分析", "算法", "数据", "推理", "模型"],
        "A": ["设计", "创意", "内容", "美学", "艺术", "表达"],
        "S": ["沟通", "助人", "教育", "服务", "协作", "用户"],
        "E": ["运营", "销售", "管理", "组织", "推进", "商业"],
        "C": ["规范", "流程", "细致", "财务", "文档", "执行"],
    }
    for k, words in lexicon.items():
        for w in words:
            if w in t:
                score[k] += 1

    ordered = sorted(score.items(), key=lambda x: x[1], reverse=True)
    top = [k for k, v in ordered if v > 0][:3]
    return "".join(top) if top else "ISC"


def _auto_fill_career_tools(st: Dict[str, Any], llm_client: LLMClient) -> None:
    merged_text = "\n".join(
        [
            st.get("resume_text", ""),
            st.get("major", ""),
            st.get("grade", ""),
            st.get("interests", ""),
            st.get("target_job", ""),
            st.get("target_reason", ""),
            st.get("communication_self_eval", ""),
            st.get("project_details", ""),
        ]
    ).strip()

    if not st.get("holland_code"):
        st["holland_code"] = _infer_holland_from_text(merged_text)

    if not st.get("mbti_type"):
        st["mbti_type"] = "ISFJ"

    if llm_client and llm_client.enabled and merged_text:
        system_prompt = "你是职业测评助手，只输出JSON，不要解释。"
        user_prompt = (
            "用户尚未做MBTI/霍兰德测评。请根据输入信息给出'初步估计'，用于职业规划起点。"
            "输出JSON字段固定为: mbti_type, holland_code, iceberg_notes。"
            "要求: mbti_type为4位字母；holland_code为3位RIASEC字母；"
            "iceberg_notes用一句中文，包含知识/技能/特质/动机中的至少2项。\n"
            f"输入: {merged_text}"
        )
        data = llm_client.generate_json(system_prompt, user_prompt)
        if isinstance(data, dict):
            mbti = str(data.get("mbti_type", "") or "").upper().strip()
            holland = str(data.get("holland_code", "") or "").upper().strip()
            note = str(data.get("iceberg_notes", "") or "").strip()

            if re.fullmatch(r"[EI][NS][FT][JP]", mbti):
                st["mbti_type"] = mbti
            if re.fullmatch(r"[RIASEC]{2,6}", holland):
                st["holland_code"] = holland[:3]
            if note:
                st["iceberg_notes"] = note

    if not st.get("iceberg_notes"):
        st["iceberg_notes"] = (
            f"初步估计：知识侧重{st.get('interests') or '目标岗位相关知识'}，"
            f"技能体现为{st.get('project_details') or '项目实践与沟通协作'}，"
            "特质偏向稳健执行与持续学习，动机来自职业成长与岗位匹配。"
        )


def _quick_assessment_questions() -> List[str]:
    return [
        "Q1/4 你更喜欢哪类任务？A分析研究 B组织推进 C沟通协作 D创意表达 E动手实操（回复字母或简短描述）",
        "Q2/4 你更偏好的工作方式？A按计划推进 B灵活探索 C独立深挖 D团队讨论",
        "Q3/4 做决定时你更看重？A数据逻辑 B感受价值 C两者都要但先逻辑 D两者都要但先感受",
        "Q4/4 你更适应哪种环境？A流程规范 B变化挑战 C研究探索 D服务他人 E现场实操",
    ]


def _score_by_text(answer: str, buckets: Dict[str, List[str]], score: Dict[str, int], step: int = 1) -> None:
    text = str(answer or "")
    upper = text.upper()
    for key, kws in buckets.items():
        for kw in kws:
            if kw.upper() in upper:
                score[key] = score.get(key, 0) + step
                break


def _run_quick_assessment(st: Dict[str, Any], llm_client: LLMClient) -> None:
    answers = st.get("assessment_answers") or {}
    q1 = str(answers.get("q1", ""))
    q2 = str(answers.get("q2", ""))
    q3 = str(answers.get("q3", ""))
    q4 = str(answers.get("q4", ""))

    mbti_score = {"E": 0, "I": 0, "S": 0, "N": 0, "T": 0, "F": 0, "J": 0, "P": 0}
    holland_score = {"R": 0, "I": 0, "A": 0, "S": 0, "E": 0, "C": 0}

    _score_by_text(q1, {
        "I": ["A", "分析", "研究", "数据", "算法", "推理"],
        "E": ["B", "组织", "推进", "管理", "商业"],
        "S": ["C", "沟通", "协作", "服务", "教学"],
        "A": ["D", "创意", "设计", "表达", "内容"],
        "R": ["E", "实操", "工程", "现场", "动手"],
    }, holland_score, step=2)
    _score_by_text(q1, {
        "T": ["分析", "研究", "算法", "工程"],
        "F": ["沟通", "服务", "表达"],
        "N": ["创意", "设计"],
        "S": ["实操", "现场"],
    }, mbti_score, step=1)

    _score_by_text(q2, {
        "J": ["A", "计划", "按计划", "稳步", "规范"],
        "P": ["B", "灵活", "探索", "变化"],
        "I": ["C", "独立", "深挖"],
        "E": ["D", "团队", "讨论"],
    }, mbti_score, step=2)
    _score_by_text(q2, {
        "C": ["A", "计划", "规范"],
        "A": ["B", "探索"],
        "I": ["C", "独立"],
        "S": ["D", "团队", "讨论"],
    }, holland_score, step=1)

    _score_by_text(q3, {
        "T": ["A", "C", "数据", "逻辑", "事实"],
        "F": ["B", "D", "感受", "价值", "关系"],
        "S": ["数据", "事实"],
        "N": ["价值", "愿景"],
    }, mbti_score, step=2)
    _score_by_text(q3, {
        "I": ["数据", "逻辑"],
        "S": ["感受", "价值", "关系"],
        "C": ["事实"],
        "A": ["价值", "愿景"],
    }, holland_score, step=1)

    _score_by_text(q4, {
        "C": ["A", "流程", "规范"],
        "E": ["B", "挑战", "快节奏", "变化"],
        "I": ["C", "研究", "探索", "实验"],
        "S": ["D", "服务", "助人", "教学"],
        "R": ["E", "现场", "实操"],
    }, holland_score, step=2)
    _score_by_text(q4, {
        "J": ["流程", "规范"],
        "P": ["变化", "挑战"],
        "I": ["研究", "探索"],
        "E": ["服务", "助人", "教学"],
        "S": ["现场", "实操"],
    }, mbti_score, step=1)

    mbti = (
        ("E" if mbti_score["E"] >= mbti_score["I"] else "I")
        + ("N" if mbti_score["N"] >= mbti_score["S"] else "S")
        + ("T" if mbti_score["T"] >= mbti_score["F"] else "F")
        + ("J" if mbti_score["J"] >= mbti_score["P"] else "P")
    )

    ordered = sorted(holland_score.items(), key=lambda x: x[1], reverse=True)
    holland_code = "".join([k for k, v in ordered if v > 0][:3]) or "ISC"

    scores_text_parts: List[str] = []
    rank_score = [90, 75, 60, 45, 35, 25]
    for idx, (k, _) in enumerate(ordered):
        scores_text_parts.append(f"{k}:{rank_score[idx]}")

    st["mbti_type"] = st.get("mbti_type") or mbti
    st["holland_code"] = st.get("holland_code") or holland_code
    st["holland_scores_text"] = " ".join(scores_text_parts)

    # Keep ice berg notes grounded in answers rather than pure guess.
    st["iceberg_notes"] = (
        f"知识偏好: {q1 or '分析/实践结合'}；技能风格: {q2 or '按场景调整'}；"
        f"价值取向: {q3 or '理性与价值并重'}；环境适配: {q4 or '可在规范与变化中切换'}。"
    )

    if llm_client and llm_client.enabled:
        # Use LLM only to polish wording, not to replace questionnaire outcome.
        system_prompt = "你是职业测评解释助手，只输出一句中文总结。"
        user_prompt = (
            "基于以下问卷结果，输出一句40-80字的解释，不要夸大，不要说是正式量表。"
            f"MBTI={st['mbti_type']}, Holland={st['holland_code']}, 回答={answers}"
        )
        refined = llm_client.generate_text(system_prompt, user_prompt, max_tokens=120)
        if refined:
            st["iceberg_notes"] = refined.strip()


def next_dialogue_turn(
    state: Dict[str, Any] | None,
    user_message: str,
    llm_client: LLMClient,
    recommend_jobs: Callable[[str], List[str]],
) -> Dict[str, Any]:
    st = default_state()
    if isinstance(state, dict):
        st.update({k: v for k, v in state.items() if k in st})

    msg = str(user_message or "").strip()

    if not msg:
        first = _friendly_ask(
            llm_client,
            goal="开启第一轮并确认是否已有简历",
            context={"step": 1},
            fallback="我们先轻松开始：你目前有简历或完整自述吗？回复“有”或“没有”都可以。",
        )
        return {"state": st, "assistant_message": first, "step": st["step"], "ready": bool(st.get("ready"))}

    node = st.get("node", "r1_has_resume")

    if node == "r1_has_resume":
        if _is_yes(msg):
            st["has_resume"] = True
            st["node"] = "r1_resume"
            q = _friendly_ask(
                llm_client,
                goal="请用户粘贴简历文本",
                context={"step": 1},
                fallback="太好了，你把简历或自述直接发我，我来帮你提炼关键信息。",
            )
            return {"state": st, "assistant_message": q, "step": 1, "ready": False}

        if _is_no(msg):
            st["has_resume"] = False
            st["node"] = "r1_major"
            q = _friendly_ask(
                llm_client,
                goal="采集专业",
                context={"step": 1},
                fallback="没问题，我们一步一步来。先告诉我你的专业是什么？",
            )
            return {"state": st, "assistant_message": q, "step": 1, "ready": False}

        q = _friendly_ask(
            llm_client,
            goal="要求明确有无简历",
            context={"step": 1},
            fallback="我收到了，你可以简单回“有”或“没有”，我就继续下一步。",
        )
        return {"state": st, "assistant_message": q, "step": 1, "ready": False}

    if node == "r1_resume":
        st["resume_text"] = msg
        if len(msg) < 20:
            q = _friendly_ask(
                llm_client,
                goal="提醒补充更完整的简历内容",
                context={"len": len(msg)},
                fallback="这段信息有点短，能再补充下项目经历、技能和目标方向吗？",
            )
            return {"state": st, "assistant_message": q, "step": 1, "ready": False}

        st["recommended_jobs"] = recommend_jobs(st["resume_text"])
        prefill = _extract_resume_prefill(st["resume_text"], llm_client)
        for k, v in prefill.items():
            if v and not st.get(k):
                st[k] = v
        return _ask_next_missing_after_resume(st, llm_client)

    if node == "r1_major":
        st["major"] = msg
        st["node"] = "r1_grade"
        q = _friendly_ask(
            llm_client,
            goal="采集年级",
            context={"major": st["major"]},
            fallback="收到，那你现在是大几或研几呢？",
        )
        return {"state": st, "assistant_message": q, "step": 1, "ready": False}

    if node == "r1_grade":
        st["grade"] = msg
        st["node"] = "r1_interests"
        q = _friendly_ask(
            llm_client,
            goal="采集兴趣方向",
            context={"major": st["major"], "grade": st["grade"]},
            fallback="明白了。你目前更感兴趣的方向是什么，比如数据、开发、产品或运营？",
        )
        return {"state": st, "assistant_message": q, "step": 1, "ready": False}

    if node == "r1_interests":
        st["interests"] = msg
        st["step"] = 2
        st["node"] = "r2_target"
        stage1_text = "\n".join([f"专业: {st['major']}", f"年级: {st['grade']}", f"兴趣方向: {st['interests']}"])
        st["recommended_jobs"] = recommend_jobs(stage1_text)
        jobs_text = "、".join(st["recommended_jobs"]) if st["recommended_jobs"] else "暂无明确推荐"
        q = _friendly_ask(
            llm_client,
            goal="开始第二轮岗位确认",
            context={"recommended_jobs": st["recommended_jobs"]},
            fallback=f"结合你的情况，我建议先关注：{jobs_text}。你最想先尝试哪个岗位？没想好也没关系。",
        )
        return {"state": st, "assistant_message": q, "step": 2, "ready": False}

    if node == "r2_target":
        if _is_no_target(msg):
            st["mode"] = "explore"
            st["node"] = "r2_explore_work"
            q = _friendly_ask(
                llm_client,
                goal="没有目标时进入探索问题1",
                context={},
                fallback="完全正常，我们先做探索。你更愿意做哪类事情：写代码、分析数据、沟通协调、产品策划还是设计创作？",
            )
            return {"state": st, "assistant_message": q, "step": 2, "ready": False}

        st["mode"] = "targeted"
        st["target_job"] = _infer_target_job(msg, st.get("recommended_jobs", []))
        if st.get("has_resume"):
            return _ask_next_missing_after_resume(st, llm_client)
        st["node"] = "r2_reason"
        q = _friendly_ask(
            llm_client,
            goal="追问目标岗位原因",
            context={"target_job": st["target_job"]},
            fallback="这个选择不错。你优先它的原因是什么？可以说兴趣、已有能力或发展空间。",
        )
        return {"state": st, "assistant_message": q, "step": 2, "ready": False}

    if node == "r2_reason":
        st["target_reason"] = msg
        if st.get("has_resume"):
            return _ask_next_missing_after_resume(st, llm_client)
        st["node"] = "r2_range"
        q = _friendly_ask(
            llm_client,
            goal="追问可接受范围",
            context={"target_job": st["target_job"]},
            fallback="了解了。那你的可接受范围是什么，比如同类岗位、行业方向或城市？",
        )
        return {"state": st, "assistant_message": q, "step": 2, "ready": False}

    if node == "r2_range":
        st["target_range"] = msg
        if st.get("has_resume"):
            return _ask_next_missing_after_resume(st, llm_client)
        st["step"] = 3
        st["node"] = "r3_communication"
        q = _friendly_ask(
            llm_client,
            goal="开启第三轮沟通能力自评",
            context={},
            fallback="第二轮完成了。第三轮先来一个轻量自评：你觉得自己的沟通协作能力大概在什么水平？",
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": False}

    if node == "r2_explore_work":
        st["explore_work_type"] = msg
        st["node"] = "r2_explore_priority"
        q = _friendly_ask(
            llm_client,
            goal="探索问题2 优先条件",
            context={"explore_work_type": st["explore_work_type"]},
            fallback="好方向。你目前最看重哪些条件：城市、薪资、稳定、成长速度还是行业？",
        )
        return {"state": st, "assistant_message": q, "step": 2, "ready": False}

    if node == "r2_explore_priority":
        st["explore_priority"] = msg
        st["node"] = "r2_explore_pick"
        jobs_text = "、".join(st.get("recommended_jobs", [])) if st.get("recommended_jobs") else "暂无明确推荐"
        q = _friendly_ask(
            llm_client,
            goal="探索问题3 选择试跑岗位",
            context={"recommended_jobs": st.get("recommended_jobs", [])},
            fallback=f"基于你的偏好，建议先从这些岗位试跑：{jobs_text}。你想先选哪一个？",
        )
        return {"state": st, "assistant_message": q, "step": 2, "ready": False}

    if node == "r2_explore_pick":
        st["target_job"] = _infer_target_job(msg, st.get("recommended_jobs", []))
        st["target_reason"] = f"探索偏好：{st.get('explore_work_type', '未填')}；优先条件：{st.get('explore_priority', '未填')}"
        st["target_range"] = msg
        if st.get("has_resume"):
            return _ask_next_missing_after_resume(st, llm_client)
        st["step"] = 3
        st["node"] = "r3_communication"
        q = _friendly_ask(
            llm_client,
            goal="开启第三轮沟通能力自评",
            context={"target_job": st["target_job"]},
            fallback="很好，方向先定下来了。第三轮先做个沟通协作能力自评吧。",
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": False}

    if node == "r3_communication":
        st["communication_self_eval"] = msg
        if st.get("has_resume"):
            return _ask_next_missing_after_resume(st, llm_client)
        st["node"] = "r3_project"
        q = _friendly_ask(
            llm_client,
            goal="追问项目经历细节",
            context={},
            fallback="谢谢你的反馈。再补充一个项目经历：你做了什么、产出是什么、结果如何？",
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": False}

    if node == "r3_project":
        st["project_details"] = msg
        if st.get("has_resume"):
            return _ask_next_missing_after_resume(st, llm_client)
        st["node"] = "r3_career_tools"
        q = _friendly_ask(
            llm_client,
            goal="补充职业规划测评工具结果",
            context={},
            fallback="最后一个补充：你做过MBTI、霍兰德或能力素质冰山测评吗？有结果就发我，没有回复“没有”即可。",
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": False}

    if node == "r3_career_tools":
        if _explicit_skip_tools(msg):
            st["iceberg_notes"] = st.get("iceberg_notes") or "用户明确选择暂不进行测评。"
            st["node"] = "ready"
            st["ready"] = True
            q = _friendly_ask(
                llm_client,
                goal="用户选择暂不测评后收束",
                context={},
                fallback="好的，我们先不做测评。你现在可以直接生成完整报告。",
            )
            return {"state": st, "assistant_message": q, "step": 3, "ready": True}

        if _is_no(msg):
            st["node"] = "r3_career_tools_optin"
            q = _friendly_ask(
                llm_client,
                goal="用户未做测评时确认是否需要系统代做",
                context={},
                fallback="没问题。如果你愿意，我可以带你做4个快速问题，给出初步MBTI和霍兰德解释。要现在做吗？",
            )
            return {"state": st, "assistant_message": q, "step": 3, "ready": False}

        mbti_hit = re.search(r"\b([EI][NS][FT][JP])\b", msg.upper())
        holland_hit = re.search(r"\b([RIASEC]{2,6})\b", msg.upper())
        st["mbti_type"] = mbti_hit.group(1) if mbti_hit else st.get("mbti_type", "")
        st["holland_code"] = holland_hit.group(1)[:3] if holland_hit else st.get("holland_code", "")
        st["iceberg_notes"] = msg

        st["node"] = "ready"
        st["ready"] = True
        q = _friendly_ask(
            llm_client,
            goal="提示可以生成报告",
            context={"target_job": st.get("target_job")},
            fallback="已完成信息采集，职业测评部分也已处理。现在可以点击“生成完整《职业生涯发展报告》”了。",
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": True}

    if node == "r3_career_tools_optin":
        if _is_yes(msg):
            st["node"] = "r3_assess_q1"
            st["assessment_answers"] = st.get("assessment_answers") or {}
            q = _quick_assessment_questions()[0]
            return {"state": st, "assistant_message": q, "step": 3, "ready": False}

        if _is_no(msg) or _explicit_skip_tools(msg):
            st["iceberg_notes"] = st.get("iceberg_notes") or "用户选择不进行测评。"
            st["node"] = "ready"
            st["ready"] = True
            q = _friendly_ask(
                llm_client,
                goal="用户不做测评时提示可继续",
                context={},
                fallback="好的，我们不做测评，后续分析会基于你已提供的信息进行。现在可以生成完整报告。",
            )
            return {"state": st, "assistant_message": q, "step": 3, "ready": True}

        mbti_hit = re.search(r"\b([EI][NS][FT][JP])\b", msg.upper())
        holland_hit = re.search(r"\b([RIASEC]{2,6})\b", msg.upper())
        if mbti_hit or holland_hit:
            st["mbti_type"] = mbti_hit.group(1) if mbti_hit else st.get("mbti_type", "")
            st["holland_code"] = holland_hit.group(1)[:3] if holland_hit else st.get("holland_code", "")
            st["iceberg_notes"] = msg
            st["node"] = "ready"
            st["ready"] = True
            q = _friendly_ask(
                llm_client,
                goal="收到用户补充测评结果并收束",
                context={},
                fallback="收到，你的测评结果已记录。现在可以生成完整报告。",
            )
            return {"state": st, "assistant_message": q, "step": 3, "ready": True}

        q = _friendly_ask(
            llm_client,
            goal="再次确认是否代做测评",
            context={},
            fallback="我可以现在帮你做初步测评，回复“要”；如果不做，回复“不要”即可。",
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": False}

    if node == "r3_assess_q1":
        (st.get("assessment_answers") or {}).update({"q1": msg})
        st["node"] = "r3_assess_q2"
        return {"state": st, "assistant_message": _quick_assessment_questions()[1], "step": 3, "ready": False}

    if node == "r3_assess_q2":
        (st.get("assessment_answers") or {}).update({"q2": msg})
        st["node"] = "r3_assess_q3"
        return {"state": st, "assistant_message": _quick_assessment_questions()[2], "step": 3, "ready": False}

    if node == "r3_assess_q3":
        (st.get("assessment_answers") or {}).update({"q3": msg})
        st["node"] = "r3_assess_q4"
        return {"state": st, "assistant_message": _quick_assessment_questions()[3], "step": 3, "ready": False}

    if node == "r3_assess_q4":
        (st.get("assessment_answers") or {}).update({"q4": msg})
        _run_quick_assessment(st, llm_client)
        st["node"] = "ready"
        st["ready"] = True
        q = _friendly_ask(
            llm_client,
            goal="测评完成后给出谨慎说明",
            context={"mbti": st.get("mbti_type"), "holland": st.get("holland_code")},
            fallback=(
                f"测评已完成：MBTI初步倾向 {st.get('mbti_type') or '待校准'}，"
                f"霍兰德代码 {st.get('holland_code') or '待校准'}。"
                "这是一版基于问答的快速估计，不是正式量表结果。现在可以生成完整报告。"
            ),
        )
        return {"state": st, "assistant_message": q, "step": 3, "ready": True}

    # ready or unknown
    st["ready"] = bool(st.get("ready"))
    q = _friendly_ask(
        llm_client,
        goal="保持温和提醒",
        context={"ready": st.get("ready")},
        fallback="如果你准备好了，就点击“生成完整《职业生涯发展报告》”；也可以继续补充信息。",
    )
    return {"state": st, "assistant_message": q, "step": int(st.get("step", 3) or 3), "ready": bool(st.get("ready"))}
