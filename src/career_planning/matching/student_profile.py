from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from ..ai.llm_client import LLMClient

SKILL_TERMS = [
    "Python", "Java", "C++", "SQL", "Vue", "React", "Node", "Docker", "Kubernetes",
    "机器学习", "深度学习", "NLP", "大模型", "RAG", "Agent", "数据分析", "算法", "测试",
]
CERT_TERMS = ["证书", "软考", "PMP", "CET", "计算机等级", "华为认证", "AWS", "阿里云", "ACP"]
COMMON_CITIES = ["北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "武汉", "西安", "重庆", "天津", "长沙", "合肥", "青岛", "郑州"]


MBTI_DICHOTOMY = {
    "E": "外向(E): 倾向从外部互动中获得能量",
    "I": "内向(I): 倾向从独处与深度思考中恢复能量",
    "S": "实感(S): 关注事实细节与可落地经验",
    "N": "直觉(N): 关注趋势可能性与抽象模式",
    "T": "思考(T): 决策偏逻辑与一致性",
    "F": "情感(F): 决策偏价值感受与关系影响",
    "J": "判断(J): 偏好计划性与节奏可控",
    "P": "知觉(P): 偏好灵活性与探索空间",
}

HOLLAND_LABELS = {
    "R": "现实型(R): 偏好动手实作、设备与现场问题",
    "I": "研究型(I): 偏好分析研究、逻辑推理与问题拆解",
    "A": "艺术型(A): 偏好创意表达、内容设计与非标准化任务",
    "S": "社会型(S): 偏好沟通协作、助人与服务场景",
    "E": "企业型(E): 偏好组织推进、影响他人与目标达成",
    "C": "传统型(C): 偏好流程规范、细节执行与秩序管理",
}

MBTI_TYPE_HINT = {
    "INTJ": ("战略型规划者", ["系统分析", "长期规划", "独立推进"], ["沟通表达显得直接", "协作耐心不足"], "每周做一次对外表达训练。"),
    "INTP": ("逻辑型探索者", ["抽象建模", "问题拆解", "快速学习"], ["执行收尾不足", "目标波动"], "用里程碑管理执行节奏。"),
    "ENTJ": ("目标型组织者", ["推进决策", "资源整合", "结果导向"], ["倾听不足", "压迫感强"], "重要沟通先做需求复述。"),
    "ENTP": ("创新型辩证者", ["创意发散", "机会识别", "快速试错"], ["持续深耕不足", "易分心"], "限定并行任务数量，保留一条主线。"),
    "INFJ": ("洞察型引导者", ["共情洞察", "长期愿景", "价值驱动"], ["压力内耗", "过度理想化"], "把目标拆到可执行的周任务。"),
    "INFP": ("价值型创作者", ["创意表达", "同理沟通", "自我驱动"], ["抗冲突弱", "执行稳定性波动"], "设定固定复盘节点，提高完成率。"),
    "ENFJ": ("协同型推动者", ["团队激励", "关系协调", "沟通影响"], ["容易过度承担", "边界感不足"], "明确角色边界，避免过载。"),
    "ENFP": ("热情型连接者", ["创意联想", "社交连接", "感染力"], ["细节耐心不足", "优先级漂移"], "采用番茄钟处理细节任务。"),
    "ISTJ": ("稳健型执行者", ["规范执行", "责任感", "细节把控"], ["变化适应慢", "创新表达弱"], "定期参与跨领域交流提升开放度。"),
    "ISFJ": ("支持型守护者", ["协作配合", "服务意识", "稳定交付"], ["不善自我展示", "回避冲突"], "每次项目主动汇报一次成果。"),
    "ESTJ": ("管理型组织者", ["组织管理", "流程优化", "执行推进"], ["灵活性不足", "倾听深度不足"], "决策前先收集团队反例。"),
    "ESFJ": ("关系型协调者", ["团队支持", "沟通协作", "服务导向"], ["容易受评价影响", "边界模糊"], "建立优先级清单，先完成关键事项。"),
    "ISTP": ("问题型实干者", ["动手实践", "故障排查", "临场应变"], ["长期规划弱", "表达偏简略"], "为长期目标补充阶段计划。"),
    "ISFP": ("审美型实践者", ["体验设计", "创意实现", "同理表达"], ["目标定义不足", "抗压波动"], "明确季度目标与产出标准。"),
    "ESTP": ("行动型开拓者", ["快速执行", "机会捕捉", "临场沟通"], ["规划不足", "细节忽略"], "在行动前先完成风险清单。"),
    "ESFP": ("表现型协作者", ["人际互动", "氛围营造", "现场应对"], ["长期专注弱", "结构化不足"], "用任务看板提高结构化能力。"),
}


def _extract_mbti_type(text: str) -> str:
    hit = re.search(r"\b([EI][NS][FT][JP])\b", text.upper())
    return hit.group(1) if hit else ""


def _extract_holland_scores(text: str) -> Dict[str, Any]:
    mapping = {
        "R": [r"现实型", r"\bR\b"],
        "I": [r"研究型", r"\bI\b"],
        "A": [r"艺术型", r"\bA\b"],
        "S": [r"社会型", r"\bS\b"],
        "E": [r"企业型", r"\bE\b"],
        "C": [r"传统型", r"\bC\b"],
    }
    scores: Dict[str, int] = {}

    for code, patterns in mapping.items():
        for p in patterns:
            m = re.search(rf"{p}\s*[（(]?[A-Z]?[）)]?\s*[:：]?\s*(\d{{1,3}})\s*分?", text, flags=re.IGNORECASE)
            if m:
                try:
                    scores[code] = max(0, min(100, int(m.group(1))))
                    break
                except Exception:
                    continue

    if len(scores) < 2:
        code_hit = re.search(r"霍兰德[^\n]{0,80}?([RIASEC]{2,6})", text.upper())
        if code_hit:
            for idx, c in enumerate(code_hit.group(1)):
                if c not in scores:
                    scores[c] = max(20, 95 - idx * 15)

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    holland_code = "".join([k for k, _ in ordered[:3]]) if ordered else ""

    return {
        "holland_scores": scores,
        "holland_code": holland_code,
        "holland_top_types": [k for k, _ in ordered[:3]],
    }


def _extract_iceberg_notes(text: str) -> Dict[str, str]:
    keys = {
        "knowledge": [r"知识", r"knowledge"],
        "skills": [r"技能", r"skill"],
        "self_concept": [r"自我概念", r"价值观", r"role"],
        "traits": [r"特质", r"性格", r"trait"],
        "motivation": [r"动机", r"驱动力", r"motivation"],
    }
    out = {
        "knowledge": "",
        "skills": "",
        "self_concept": "",
        "traits": "",
        "motivation": "",
    }

    for k, pats in keys.items():
        for p in pats:
            m = re.search(rf"{p}[^\n:：]{{0,10}}[:：]\s*([^\n。；;]{{2,80}})", text, flags=re.IGNORECASE)
            if m:
                out[k] = m.group(1).strip()
                break

    generic = re.search(r"能力素质冰山补充[:：]\s*([^\n]{{4,200}})", text, flags=re.IGNORECASE)
    if generic:
        note = generic.group(1).strip()
        if note and not out["self_concept"]:
            out["self_concept"] = note

    if "冰山" in text and not any(out.values()):
        out["self_concept"] = "已提及能力素质冰山模型"

    return out


def _build_mbti_detail(mbti_type: str) -> Dict[str, Any]:
    mbti = str(mbti_type or "").upper().strip()
    if not re.fullmatch(r"[EI][NS][FT][JP]", mbti):
        return {
            "type": "",
            "label": "",
            "dimension_notes": [],
            "strengths": [],
            "watchouts": [],
            "development_advice": "",
        }

    desc = MBTI_TYPE_HINT.get(mbti)
    if desc:
        label, strengths, watchouts, advice = desc
    else:
        label, strengths, watchouts, advice = ("综合型", ["适应能力较平衡"], ["需结合真实行为校准"], "结合项目反馈持续校准类型。")

    notes = [MBTI_DICHOTOMY.get(ch, "") for ch in mbti]
    return {
        "type": mbti,
        "label": label,
        "dimension_notes": [x for x in notes if x],
        "strengths": strengths,
        "watchouts": watchouts,
        "development_advice": advice,
    }


def _enrich_iceberg_model(iceberg: Dict[str, str], text: str, profile: Dict[str, Any]) -> Dict[str, str]:
    out = {k: str(v or "").strip() for k, v in (iceberg or {}).items()}
    out.setdefault("knowledge", "")
    out.setdefault("skills", "")
    out.setdefault("self_concept", "")
    out.setdefault("traits", "")
    out.setdefault("motivation", "")

    if not out["knowledge"]:
        major = ""
        m = re.search(r"(专业|主修)[:：]?\s*([^\n。；;]{2,30})", text, flags=re.IGNORECASE)
        if m:
            major = m.group(2).strip()
        out["knowledge"] = f"{major}相关基础知识与岗位通识" if major else "目标岗位相关基础知识与行业认知"

    if not out["skills"]:
        skills = profile.get("skills", []) or []
        out["skills"] = "、".join(skills[:4]) if skills else "项目实践、沟通协作与问题拆解能力"

    if not out["self_concept"]:
        out["self_concept"] = "重视成长反馈，愿意通过迭代提升岗位匹配度"

    if not out["traits"]:
        mbti = str(profile.get("mbti_type", "") or "").upper()
        if mbti:
            out["traits"] = f"性格倾向{mbti}，做事风格可通过真实项目持续校准"
        else:
            out["traits"] = "具备一定自驱与执行意识，需在压力场景中继续验证"

    if not out["motivation"]:
        target = str(profile.get("employment_intention", "") or "")
        out["motivation"] = f"通过持续学习进入{target}方向并获得长期成长" if target else "通过职业探索明确方向并建立长期成长路径"

    return out


def _build_holland_detail(holland_code: str, holland_scores: Dict[str, Any]) -> Dict[str, Any]:
    code = str(holland_code or "").upper().strip()
    letters = [c for c in code if c in HOLLAND_LABELS]

    score_pairs: List[tuple[str, int]] = []
    if isinstance(holland_scores, dict):
        for k, v in holland_scores.items():
            try:
                score_pairs.append((str(k).upper(), int(v)))
            except Exception:
                continue
    if score_pairs:
        score_pairs.sort(key=lambda x: x[1], reverse=True)

    top = letters[:3]
    if not top and score_pairs:
        top = [k for k, _ in score_pairs[:3]]

    meanings = [HOLLAND_LABELS[c] for c in top if c in HOLLAND_LABELS]
    if not meanings:
        meanings = ["暂无霍兰德代码解释，请补充测评结果或完成快速测评。"]

    role_hint_map = {
        "R": ["工程实施", "运维与现场支持", "测试与质量"],
        "I": ["研发与算法", "数据分析", "研究型岗位"],
        "A": ["产品设计", "内容创作", "用户体验"],
        "S": ["客户成功", "教学培训", "咨询与服务"],
        "E": ["产品运营", "项目管理", "业务拓展"],
        "C": ["财务与审计", "流程管理", "行政与文档体系"],
    }

    fit_roles: List[str] = []
    for c in top:
        fit_roles.extend(role_hint_map.get(c, []))

    watchouts = [
        "霍兰德代码用于兴趣倾向，不等同于能力高低。",
        "若与真实项目反馈冲突，应优先参考实际表现并动态校准。",
    ]

    return {
        "code": code,
        "meanings": meanings,
        "fit_roles": fit_roles[:6],
        "watchouts": watchouts,
    }


def _extract_academic_stage(text: str) -> Dict[str, str]:
    stage_map = [
        ("freshman", "大一", [r"\b大一\b", r"本科一年级", r"大学一年级", r"新生"]),
        ("sophomore", "大二", [r"\b大二\b", r"本科二年级", r"大学二年级"]),
        ("junior", "大三", [r"\b大三\b", r"本科三年级", r"大学三年级"]),
        ("senior", "大四", [r"\b大四\b", r"本科四年级", r"大学四年级", r"毕业年级"]),
    ]
    for code, label, patterns in stage_map:
        if any(re.search(p, text, flags=re.IGNORECASE) for p in patterns):
            return {"academic_stage": code, "academic_stage_label": label}

    if re.search(r"研一|硕士一年级|研究生一年级", text, flags=re.IGNORECASE):
        return {"academic_stage": "graduate_first", "academic_stage_label": "研一"}
    if re.search(r"研二|硕士二年级|研究生二年级", text, flags=re.IGNORECASE):
        return {"academic_stage": "graduate_second", "academic_stage_label": "研二"}
    if re.search(r"研三|博士|研究生", text, flags=re.IGNORECASE):
        return {"academic_stage": "graduate", "academic_stage_label": "研究生"}

    return {"academic_stage": "unknown", "academic_stage_label": "未识别"}


def _find_terms(text: str, terms: List[str], limit: int) -> List[str]:
    lower = text.lower()
    hits: List[str] = []
    for term in terms:
        if term.lower() in lower and term not in hits:
            hits.append(term)
        if len(hits) >= limit:
            break
    return hits


def _count_patterns(text: str, patterns: List[str]) -> int:
    score = 0
    for pattern in patterns:
        score += len(re.findall(pattern, text, flags=re.IGNORECASE))
    return score


def _score_soft_dimension(
    text: str,
    positive_patterns: List[str],
    evidence_patterns: List[str],
    negative_patterns: List[str],
) -> float:
    pos_hits = _count_patterns(text, positive_patterns)
    evidence_hits = _count_patterns(text, evidence_patterns)
    neg_hits = _count_patterns(text, negative_patterns)

    base = 0.2
    if pos_hits > 0:
        base += 0.45
    base += min(0.28, evidence_hits * 0.07)
    base -= min(0.38, neg_hits * 0.12)

    return round(max(0.0, min(1.0, base)), 2)


def build_student_profile(raw_text: str, llm: LLMClient | None = None) -> Dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {
            "skills": [],
            "certificates": [],
            "mbti_type": "",
            "mbti_detail": {
                "type": "",
                "label": "",
                "dimension_notes": [],
                "strengths": [],
                "watchouts": [],
                "development_advice": "",
            },
            "holland_code": "",
            "holland_scores": {},
            "holland_top_types": [],
            "holland_detail": {
                "code": "",
                "meanings": [],
                "fit_roles": [],
                "watchouts": [],
            },
            "iceberg_model": {
                "knowledge": "",
                "skills": "",
                "self_concept": "",
                "traits": "",
                "motivation": "",
            },
            "academic_stage": "unknown",
            "academic_stage_label": "未识别",
            "innovation_ability": 0.0,
            "learning_ability": 0.0,
            "stress_tolerance": 0.0,
            "communication_ability": 0.0,
            "internship_ability": 0.0,
            "employment_intention": "",
            "target_city": "",
            "expected_salary_k": 0,
            "completeness_score": 0,
            "competitiveness_score": 0,
            "summary": "",
        }

    skills = _find_terms(text, SKILL_TERMS, 12)
    certs = _find_terms(text, CERT_TERMS, 5)
    stage_info = _extract_academic_stage(text)
    mbti_type = _extract_mbti_type(text)
    holland = _extract_holland_scores(text)
    iceberg = _extract_iceberg_notes(text)

    innovation_score = _score_soft_dimension(
        text,
        positive_patterns=[r"创新能力[强好佳]", r"擅长优化", r"改进", r"技术方案", r"独立设计"],
        evidence_patterns=[r"优化", r"重构", r"性能提升", r"开源", r"专利", r"设计"],
        negative_patterns=[r"创新能力[弱差不足]", r"缺乏创新", r"没有创新"],
    )
    learning_score = _score_soft_dimension(
        text,
        positive_patterns=[r"学习能力[强好佳]", r"学习主动", r"自学能力", r"持续学习"],
        evidence_patterns=[r"学习", r"自学", r"课程", r"复盘", r"研究", r"总结"],
        negative_patterns=[r"学习能力[弱差不足]", r"学习慢", r"不愿学习"],
    )
    stress_score = _score_soft_dimension(
        text,
        positive_patterns=[r"抗压能力[强好佳]", r"抗压能力好", r"心态稳定", r"能扛压"],
        evidence_patterns=[r"项目冲刺", r"高强度", r"紧急", r"故障", r"加班", r"deadline"],
        negative_patterns=[r"抗压能力[弱差不足]", r"抗压能力低", r"压力大.*崩", r"容易焦虑"],
    )
    communication_score = _score_soft_dimension(
        text,
        positive_patterns=[r"沟通[顺畅良好]", r"善于沟通", r"表达清晰", r"团队协作[强好佳]"],
        evidence_patterns=[r"沟通", r"协作", r"汇报", r"跨部门", r"倾听需求", r"技术方案"],
        negative_patterns=[r"沟通能力[弱差不足]", r"不善沟通", r"表达不清"],
    )
    internship_score = _score_soft_dimension(
        text,
        positive_patterns=[r"实习经历", r"项目经验丰富", r"实践能力[强好佳]", r"竞赛经历", r"实验室"],
        evidence_patterns=[r"实习", r"项目", r"竞赛", r"实践", r"上线", r"交付", r"社团", r"实验室", r"课程设计"],
        negative_patterns=[r"实践经验不足"],
    )

    profile = {
        "skills": skills,
        "certificates": certs,
        "mbti_type": mbti_type,
        "mbti_detail": _build_mbti_detail(mbti_type),
        "holland_code": holland["holland_code"],
        "holland_scores": holland["holland_scores"],
        "holland_top_types": holland["holland_top_types"],
        "holland_detail": _build_holland_detail(holland["holland_code"], holland["holland_scores"]),
        "iceberg_model": iceberg,
        "academic_stage": stage_info["academic_stage"],
        "academic_stage_label": stage_info["academic_stage_label"],
        "innovation_ability": innovation_score,
        "learning_ability": learning_score,
        "stress_tolerance": stress_score,
        "communication_ability": communication_score,
        "internship_ability": internship_score,
        "employment_intention": "",
        "target_city": "",
        "expected_salary_k": 0,
        "completeness_score": 0,
        "competitiveness_score": 0,
        "summary": "",
    }

    # Prefer LLM extraction for natural language input; regex remains as fallback.
    llm_pref = _extract_preferences_with_llm(text, llm)
    if llm_pref.get("employment_intention"):
        profile["employment_intention"] = llm_pref["employment_intention"]
    if llm_pref.get("target_city"):
        profile["target_city"] = llm_pref["target_city"]
    if llm_pref.get("expected_salary_k", 0) > 0:
        profile["expected_salary_k"] = int(llm_pref["expected_salary_k"])

    if llm_pref.get("mbti_type") and not profile["mbti_type"]:
        profile["mbti_type"] = str(llm_pref["mbti_type"]).upper()
    profile["mbti_detail"] = _build_mbti_detail(profile["mbti_type"])
    if llm_pref.get("holland_code") and not profile["holland_code"]:
        profile["holland_code"] = str(llm_pref["holland_code"]).upper()
    profile["holland_detail"] = _build_holland_detail(profile["holland_code"], profile.get("holland_scores", {}))

    intent_match = re.search(r"(目标岗位|求职意向|意向岗位|目标方向)[:：]?\s*([^\n。；;]{2,40})", text)
    if intent_match and not profile["employment_intention"]:
        profile["employment_intention"] = intent_match.group(2).strip()

    city_match = re.search(r"(目标城市|意向城市|工作城市|求职城市)[:：]?\s*([^\n。；;]{2,20})", text)
    if city_match and not profile["target_city"]:
        profile["target_city"] = city_match.group(2).strip()

    salary_match = re.search(r"(期望薪资|薪资期望|期望月薪)[:：]?\s*(\d{1,2})\s*[kK]", text)
    if salary_match and profile["expected_salary_k"] <= 0:
        profile["expected_salary_k"] = int(salary_match.group(2))

    if not profile["employment_intention"]:
        free_intent = re.search(
            r"(?:想做|想找|应聘|求职|目标是|目标岗位是|意向|希望从事)\s*([\u4e00-\u9fa5A-Za-z0-9+/]{2,24}(?:工程师|分析师|开发|测试|算法|产品经理|运营|设计))",
            text,
            flags=re.IGNORECASE,
        )
        if free_intent:
            profile["employment_intention"] = free_intent.group(1).strip()

    if not profile["target_city"]:
        for city in COMMON_CITIES:
            if city in text:
                profile["target_city"] = city
                break

    if profile["expected_salary_k"] <= 0:
        free_salary = re.search(r"(\d{1,2})\s*[kK]\s*(?:-|到|~|至)\s*(\d{1,2})\s*[kK]", text)
        if free_salary:
            low = int(free_salary.group(1))
            high = int(free_salary.group(2))
            profile["expected_salary_k"] = int(round((low + high) / 2))

    profile["iceberg_model"] = _enrich_iceberg_model(profile.get("iceberg_model", {}), text, profile)

    dimensions = [
        bool(profile["skills"]),
        bool(profile["certificates"]),
        profile["innovation_ability"] > 0,
        profile["learning_ability"] > 0,
        profile["stress_tolerance"] > 0,
        profile["communication_ability"] > 0,
        profile["internship_ability"] > 0,
        bool(profile["employment_intention"]),
        bool(profile["target_city"]),
    ]
    profile["completeness_score"] = int(round(sum(dimensions) / len(dimensions) * 100))

    profile["competitiveness_score"] = int(
        round(
            min(
                1.0,
                0.35 * (len(profile["skills"]) / 10)
                + 0.1 * (len(profile["certificates"]) / 4)
                + 0.15 * profile["innovation_ability"]
                + 0.15 * profile["learning_ability"]
                + 0.1 * profile["communication_ability"]
                + 0.15 * profile["internship_ability"],
            )
            * 100
        )
    )

    if llm and llm.enabled:
        summary = llm.generate_text(
            "你是职业规划顾问，提炼学生画像。",
            "请根据以下简历文本输出80字以内中文总结，聚焦能力和求职意愿:\n" + text,
            max_tokens=200,
        )
        profile["summary"] = summary or "根据输入信息生成了基础画像。"
    else:
        profile["summary"] = "已基于文本提取技能、证书与素养维度画像。"

    return profile


def _extract_preferences_with_llm(text: str, llm: LLMClient | None) -> Dict[str, Any]:
    if not llm or not llm.enabled:
        return {}

    system_prompt = "你是简历信息抽取助手，只输出JSON。"
    user_prompt = (
        "请从以下文本中抽取求职偏好信息，并输出JSON，字段固定为: "
        "employment_intention(字符串), target_city(字符串), expected_salary_k(整数，单位K，没有则为0), "
        "mbti_type(字符串), holland_code(字符串)。"
        "不要输出任何额外解释。\n"
        f"文本: {text}"
    )

    raw = llm.generate_text(system_prompt, user_prompt, max_tokens=220)
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            data = json.loads(raw[start : end + 1])
        except Exception:
            return {}

    if not isinstance(data, dict):
        return {}

    out = {
        "employment_intention": str(data.get("employment_intention", "")).strip(),
        "target_city": str(data.get("target_city", "")).strip(),
        "expected_salary_k": 0,
        "mbti_type": str(data.get("mbti_type", "")).strip(),
        "holland_code": str(data.get("holland_code", "")).strip(),
    }

    try:
        out["expected_salary_k"] = int(data.get("expected_salary_k", 0) or 0)
    except Exception:
        out["expected_salary_k"] = 0

    return out
