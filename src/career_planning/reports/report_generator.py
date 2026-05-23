from __future__ import annotations

import html
import importlib
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Iterable


def _clamp_score(value: Any, default: float = 60.0) -> float:
    try:
        num = float(value)
    except Exception:
        num = float(default)
    return max(0.0, min(100.0, num))


def _build_rule_ability_radar(student_profile: Dict[str, Any], matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    axes = [
        "专业基础",
        "专业技能",
        "发展潜力",
        "职业素养",
        "沟通协作",
        "抗压能力",
        "创新能力",
    ]

    top = matches[0] if matches else {}
    dims = top.get("dimension_scores", {}) if isinstance(top, dict) else {}

    communication = _clamp_score(student_profile.get("communication_ability", 62), default=62)
    stress = _clamp_score(student_profile.get("stress_tolerance", 58), default=58)
    innovation = _clamp_score(student_profile.get("innovation_ability", 66), default=66)

    current_values = [
        _clamp_score(dims.get("foundation_requirements", 68), default=68),
        _clamp_score(dims.get("professional_skills", 66), default=66),
        _clamp_score(dims.get("development_potential", 70), default=70),
        _clamp_score(dims.get("professional_quality", 65), default=65),
        communication,
        stress,
        innovation,
    ]

    target_values = [
        min(100.0, max(75.0, current_values[0] + 8.0)),
        min(100.0, max(78.0, current_values[1] + 8.0)),
        min(100.0, max(80.0, current_values[2] + 6.0)),
        min(100.0, max(78.0, current_values[3] + 8.0)),
        min(100.0, max(75.0, current_values[4] + 10.0)),
        min(100.0, max(75.0, current_values[5] + 12.0)),
        min(100.0, max(78.0, current_values[6] + 8.0)),
    ]

    return {
        "title": "就业能力画像",
        "axes": axes,
        "datasets": [
            {"name": "当前状态", "values": [round(v, 1) for v in current_values]},
            {"name": "目标线", "values": [round(v, 1) for v in target_values]},
        ],
        "minValue": 0.0,
        "maxValue": 100.0,
        "scoredBy": "rule",
    }


def build_ability_radar_data(
    student_profile: Dict[str, Any],
    matches: List[Dict[str, Any]],
    llm_client: Any | None = None,
) -> Dict[str, Any]:
    fallback = _build_rule_ability_radar(student_profile, matches)
    if not llm_client or not getattr(llm_client, "enabled", False):
        return fallback

    top = matches[:3] if isinstance(matches, list) else []
    system_prompt = (
        "你是职业能力评估专家。请根据学生画像与岗位匹配结果输出严格JSON，不要输出解释文本。"
    )
    user_prompt = (
        "请输出能力雷达图数据，JSON字段固定为: "
        "title, axes, datasets, minValue, maxValue。"
        "\n约束:"
        "\n1) axes 必须是7个维度: 专业基础, 专业技能, 发展潜力, 职业素养, 沟通协作, 抗压能力, 创新能力"
        "\n2) datasets 至少2条，第一条name=当前状态，第二条name=目标线"
        "\n3) values 与 axes 一一对应，分数范围0-100，可保留1位小数"
        "\n4) 目标线应总体高于当前状态，但提升幅度合理（通常 5-15 分）"
        "\n5) 只返回JSON对象"
        f"\n学生画像: {student_profile}"
        f"\n匹配结果Top3: {top}"
    )

    try:
        data = llm_client.generate_json(system_prompt, user_prompt)
    except Exception:
        data = {}

    if not isinstance(data, dict):
        return fallback

    axes = data.get("axes")
    datasets = data.get("datasets")
    if not isinstance(axes, list) or len(axes) != 7 or not isinstance(datasets, list) or len(datasets) < 2:
        return fallback

    normalized_axes = [str(x or "").strip() for x in axes]
    expected_axes = ["专业基础", "专业技能", "发展潜力", "职业素养", "沟通协作", "抗压能力", "创新能力"]
    if normalized_axes != expected_axes:
        return fallback

    normalized_sets: List[Dict[str, Any]] = []
    for ds in datasets[:4]:
        if not isinstance(ds, dict):
            continue
        name = str(ds.get("name", "")).strip() or "序列"
        values = ds.get("values") if isinstance(ds.get("values"), list) else []
        fixed = [_clamp_score(x, default=60) for x in values[: len(expected_axes)]]
        while len(fixed) < len(expected_axes):
            fixed.append(60.0)
        normalized_sets.append({"name": name, "values": [round(v, 1) for v in fixed]})

    if len(normalized_sets) < 2:
        return fallback

    # Ensure the first two series keep expected semantic names.
    normalized_sets[0]["name"] = "当前状态"
    normalized_sets[1]["name"] = "目标线"

    return {
        "title": str(data.get("title", "就业能力画像") or "就业能力画像"),
        "axes": expected_axes,
        "datasets": normalized_sets,
        "minValue": 0.0,
        "maxValue": 100.0,
        "scoredBy": "ai",
    }


def _build_actions(student_profile: Dict[str, Any], top_match: Dict[str, Any]) -> Dict[str, List[str]]:
    gap_skills = top_match.get("gap_skills", [])
    stage = str(student_profile.get("academic_stage", "unknown") or "unknown")

    if stage == "freshman":
        job_search_track = [
            "优先完成职业认知：每周拆解1个目标岗位JD，沉淀技能词典与学习清单。",
            "以模拟求职为主：完成基础简历初版与1次自我介绍演练。",
            "建立岗位信息输入机制：每周跟踪5个校招/实习岗位的能力要求。",
        ]
        campus_planning_track = [
            "以课程项目和社团实践为主，至少产出1个可展示作品。",
            "参加1-2项入门竞赛/训练营，补齐基础工具链（Git、SQL、Python等）。",
            "建立学期复盘节奏：每月复盘技能进度与方向匹配度。",
        ]
        mid_term = [
            "在下一学期形成方向型项目组合（2-3个），突出问题解决能力。",
            "争取进入实验室/导师项目/校企课题，积累真实协作经历。",
            "持续迭代简历与作品集，为大二下的实战机会做准备。",
        ]
    elif stage == "sophomore":
        job_search_track = [
            "开始小规模定向投递（实习/远程项目/校内岗位），每周至少3-5个目标机会。",
            "每周进行2次岗位能力训练（笔试题/业务题/项目复盘）。",
            "针对目标方向完成简历与项目描述优化，突出可量化成果。",
        ]
        campus_planning_track = [
            "以课程项目、竞赛、实验室和社团实践为核心积累，不以实习为硬性前提。",
            "围绕目标岗位补齐2-3项关键能力（如数据分析、工程化、表达协作）。",
            "每月至少参加1次行业交流活动，验证岗位偏好与学习路线。",
        ]
        mid_term = [
            "8-12周完成一个可展示的中型项目，并公开到作品集或代码仓库。",
            "优先参与真实项目协作（课程项目/实验室/校企合作）；具备条件时再尝试实习。",
            "按月复盘投递反馈，动态调整岗位优先级与能力建设顺序。",
        ]
    elif stage in ("junior", "senior", "graduate_first", "graduate_second", "graduate"):
        job_search_track = [
            "2周内完成目标岗位JD拆解，形成技能清单与证据清单。",
            "每周至少完成2次岗位定向练习（算法题/业务题/项目复盘）。",
            "投递前完成1版针对目标岗位的简历改写并进行同伴评审。",
        ]
        campus_planning_track = [
            "基于当前阶段设定学期职业目标（能力、项目、竞赛/实验室实践）并拆解到每月。",
            "每月至少参加1次职业探索活动（讲座、访谈、行业社群）并记录结论。",
            "围绕目标方向补充课程与证书计划，形成毕业前能力建设路线图。",
        ]
        mid_term = [
            "8-12周完成一个可展示的项目，并在GitHub或作品集公开。",
            "优先参与真实项目协作，结合阶段条件规划实习或校招节奏。",
            "每月复盘一次投递反馈，动态调整岗位优先级与能力建设。",
        ]
    else:
        job_search_track = [
            "2周内完成目标岗位JD拆解，形成技能清单与证据清单。",
            "每周至少完成2次岗位定向练习（算法题/业务题/项目复盘）。",
            "投递前完成1版针对目标岗位的简历改写并进行同伴评审。",
        ]
        campus_planning_track = [
            "基于当前阶段设定学期职业目标（能力、项目、竞赛/社团实践）并拆解到每月。",
            "每月至少参加1次职业探索活动（讲座、访谈、行业社群）并记录结论。",
            "围绕目标方向补充课程与证书计划，形成毕业前能力建设路线图。",
        ]
        mid_term = [
            "8-12周完成一个可展示的项目，并在GitHub或作品集公开。",
            "优先参与真实项目协作（课程项目/实验室/校企合作）；具备条件时再尝试实习。",
            "每月复盘一次投递反馈，动态调整岗位优先级与能力建设。",
        ]
    if gap_skills:
        job_search_track.append("优先补齐技能缺口: " + "、".join(gap_skills[:4]))
        campus_planning_track.append("将缺口技能纳入学期训练: " + "、".join(gap_skills[:4]))
    return {
        "job_search_track": job_search_track,
        "campus_planning_track": campus_planning_track,
        "mid_term": mid_term,
    }


def _list_to_md(items: List[str]) -> str:
    if not items:
        return "- 暂无"
    return "\n".join([f"- {i}" for i in items])


def _tool_insights(student_profile: Dict[str, Any]) -> Dict[str, Any]:
    mbti = str(student_profile.get("mbti_type", "") or "").upper()
    mbti_detail = student_profile.get("mbti_detail", {}) or {}
    holland_code = str(student_profile.get("holland_code", "") or "").upper()
    holland_scores = student_profile.get("holland_scores", {}) or {}
    holland_detail = student_profile.get("holland_detail", {}) or {}
    iceberg = student_profile.get("iceberg_model", {}) or {}

    holland_pairs = []
    if isinstance(holland_scores, dict):
        for k, v in holland_scores.items():
            holland_pairs.append(f"{k}:{v}")

    iceberg_lines = []
    labels = {
        "knowledge": "知识",
        "skills": "技能",
        "self_concept": "自我概念/价值观",
        "traits": "特质(性格)",
        "motivation": "动机",
    }
    if isinstance(iceberg, dict):
        for k, label in labels.items():
            val = str(iceberg.get(k, "") or "").strip()
            if val:
                iceberg_lines.append(f"{label}: {val}")

    return {
        "mbti": mbti,
        "mbti_label": str(mbti_detail.get("label", "") or ""),
        "mbti_dimension_notes": mbti_detail.get("dimension_notes", []) or [],
        "mbti_strengths": mbti_detail.get("strengths", []) or [],
        "mbti_watchouts": mbti_detail.get("watchouts", []) or [],
        "mbti_advice": str(mbti_detail.get("development_advice", "") or ""),
        "holland_code": holland_code,
        "holland_scores_text": "、".join(holland_pairs),
        "holland_meanings": holland_detail.get("meanings", []) or [],
        "holland_fit_roles": holland_detail.get("fit_roles", []) or [],
        "holland_watchouts": holland_detail.get("watchouts", []) or [],
        "iceberg_lines": iceberg_lines,
    }


def generate_report_markdown(
    student_profile: Dict[str, Any],
    matches: List[Dict[str, Any]],
    vertical_graph: List[Dict[str, Any]],
    transition_graph: List[Dict[str, Any]],
    llm_client: Any | None = None,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top = matches[0] if matches else {}
    actions = _build_actions(student_profile, top)
    stage_label = student_profile.get("academic_stage_label", "未识别")
    tools = _tool_insights(student_profile)

    match_rows = []
    for m in matches[:5]:
        dims = m.get("dimension_scores", {})
        row = (
            f"| {m.get('job_title', '')} | {m.get('score', 0)} | "
            f"{dims.get('foundation_requirements', 0)} | "
            f"{dims.get('professional_skills', 0)} | "
            f"{dims.get('professional_quality', 0)} | "
            f"{dims.get('development_potential', 0)} |"
        )
        match_rows.append(row)

    vertical_rows = []
    for item in vertical_graph[:8]:
        vertical_rows.append(f"- {item['job_title']}: {' -> '.join(item['path'])}")

    transition_rows = []
    for item in transition_graph:
        transition_rows.append(f"- {item['job_title']} -> {' / '.join(item['transitions'])}")

    match_rows_text = "\n".join(match_rows) if match_rows else "| 暂无 | 0 | 0 | 0 | 0 | 0 |"

    completeness = student_profile.get("completeness_score", 0)
    competitiveness = student_profile.get("competitiveness_score", 0)

    # 构造雷达图 mermaid 块，仅用于 PDF 导出识别并独立渲染。
    ability_radar = build_ability_radar_data(student_profile, matches, llm_client)
    radar_mermaid = (
        f"\n\n```mermaid\nradar-beta\n    title {ability_radar.get('title', '就业能力画像')}\n"
        "    axis \"专业基础\" [0.0, 100.0]\n"
        "    axis \"专业技能\" [0.0, 100.0]\n"
        "    axis \"发展潜力\" [0.0, 100.0]\n"
        "    axis \"职业素养\" [0.0, 100.0]\n"
        "    axis \"沟通协作\" [0.0, 100.0]\n"
        "    axis \"抗压能力\" [0.0, 100.0]\n"
        "    axis \"创新能力\" [0.0, 100.0]\n"
    )
    for ds in ability_radar.get("datasets", []):
        radar_mermaid += f"    \"{ds['name']}\": {ds['values']}\n"
    radar_mermaid += "```\n"

    fallback_report = f"""# 大学生求职与职业规划发展报告

生成时间: {now}

## 1. 学生就业能力画像

{radar_mermaid}
- 技能: {"、".join(student_profile.get("skills", [])) or "暂无"}
- 证书: {"、".join(student_profile.get("certificates", [])) or "暂无"}
- 就业意愿: {student_profile.get("employment_intention") or "未明确"}
- 画像总结: {student_profile.get("summary") or "暂无"}
- 当前阶段: {stage_label}
- 完整度评分: {completeness}/100
- 竞争力评分: {competitiveness}/100

## 2. 职业探索与人岗匹配

| 目标岗位 | 综合匹配度 | 基础要求 | 职业技能 | 职业素养 | 发展潜力 |
|---|---:|---:|---:|---:|---:|
{match_rows_text}

优势能力:
{_list_to_md(top.get("advantage_skills", []))}

关键差距:
{_list_to_md(top.get("gap_skills", []))}

## 3. 职业生涯规划工具结果（MBTI / 霍兰德 / 冰山模型）

- MBTI: {tools['mbti'] or '未提供（可选）'} {f"（{tools['mbti_label']}）" if tools['mbti_label'] else ''}
- MBTI维度解释:
{_list_to_md(tools['mbti_dimension_notes'])}
- MBTI优势画像:
{_list_to_md(tools['mbti_strengths'])}
- MBTI风险提醒:
{_list_to_md(tools['mbti_watchouts'])}
- MBTI发展建议: {tools['mbti_advice'] or '建议结合课程/项目反馈持续校准'}
- 霍兰德代码: {tools['holland_code'] or '未提供（可选）'}
- 霍兰德分数: {tools['holland_scores_text'] or '未提供（可选）'}
- 霍兰德代码解释:
{_list_to_md(tools['holland_meanings'])}
- 霍兰德匹配场景建议:
{_list_to_md(tools['holland_fit_roles'])}
- 霍兰德使用提醒:
{_list_to_md(tools['holland_watchouts'])}
- 冰山模型分层详情:
{_list_to_md(tools['iceberg_lines'])}

工具使用建议:
- 若已有测评结果，本报告直接采用并用于岗位解释。
- 若暂无测评结果，建议补测后与岗位匹配结果交叉验证，避免单一测评定结论。
- 优先关注“能力证据”是否与目标岗位一致（项目产出、协作记录、复盘质量）。

## 4. 岗位关联图谱与发展路径

### 3.1 垂直岗位图谱
{_list_to_md(vertical_rows)}

### 3.2 换岗路径图谱
{_list_to_md(transition_rows)}

## 5. 双线职业目标设定与行动计划

求职推进计划（0-3个月）:
{_list_to_md(actions["job_search_track"])}

在校职业规划（0-3个月）:
{_list_to_md(actions["campus_planning_track"])}

中期行动计划（3-12个月）:
{_list_to_md(actions["mid_term"])}

评估指标建议:
- 每月岗位投递转化率（投递-笔试-面试）
- 技能补齐进度（按技能清单完成率）
- 项目成果数量与质量（可验证链接、复盘文档）

## 6. 编辑优化与导出建议

- 内容完整性检查: 已覆盖岗位画像、能力画像、匹配分析、路径规划、行动计划。
- 编辑建议: 可补充具体公司类型偏好、城市优先级与薪资底线。
- 导出支持: 报告支持PDF、Markdown与HTML一键导出。
"""

    if not llm_client or not getattr(llm_client, "enabled", False):
        return fallback_report

    report_context = {
        "time": now,
        "student_profile": student_profile,
        "matches_top": matches[:5],
        "vertical_graph": vertical_graph[:8],
        "transition_graph": transition_graph,
        "actions": actions,
        "ability_radar_mermaid": radar_mermaid, # 明确告诉 AI 这一章节需包含雷达图块
    }

    system_prompt, user_prompt = _build_ai_report_prompt(report_context)
    ai_report = llm_client.generate_text(system_prompt, user_prompt, max_tokens=3800)

    if ai_report and "#" in ai_report and "匹配" in ai_report:
        # 补丁：确保 AI 输出中包含雷达图块以供 PDF 导出渲染
        if "radar-beta" not in ai_report:
            ai_report = ai_report.replace("## 1. 学生就业能力画像", f"## 1. 学生就业能力画像\n\n{radar_mermaid}")
        return ai_report.strip()
    return fallback_report


def stream_report_markdown(
    student_profile: Dict[str, Any],
    matches: List[Dict[str, Any]],
    vertical_graph: List[Dict[str, Any]],
    transition_graph: List[Dict[str, Any]],
    llm_client: Any | None = None,
) -> Iterable[Dict[str, str]]:
    fallback_report = generate_report_markdown(
        student_profile=student_profile,
        matches=matches,
        vertical_graph=vertical_graph,
        transition_graph=transition_graph,
        llm_client=None,
    )

    yield {"type": "stage", "message": "已拿到匹配结果，正在组织报告结构..."}
    yield {"type": "stage", "message": "正在生成报告正文，请稍候..."}

    if not llm_client or not getattr(llm_client, "enabled", False):
        for chunk in _chunk_text(fallback_report, 80):
            yield {"type": "chunk", "content": chunk}
        yield {"type": "done", "mode": "fallback"}
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top = matches[0] if matches else {}
    actions = _build_actions(student_profile, top)
    report_context = {
        "time": now,
        "student_profile": student_profile,
        "matches_top": matches[:5],
        "vertical_graph": vertical_graph[:8],
        "transition_graph": transition_graph,
        "actions": actions,
    }
    system_prompt, user_prompt = _build_ai_report_prompt(report_context)

    assembled = ""
    try:
        for piece in llm_client.stream_text(system_prompt, user_prompt, max_tokens=3800):
            if not piece:
                continue
            assembled += piece
            yield {"type": "chunk", "content": piece}

        if assembled.strip() and "#" in assembled and "匹配" in assembled:
            yield {"type": "done", "mode": "ai"}
            return
    except Exception:
        pass

    # Fallback when stream fails or content is invalid.
    if not assembled.strip():
        for chunk in _chunk_text(fallback_report, 80):
            yield {"type": "chunk", "content": chunk}
    else:
        missing = "\n\n## 说明\n\nAI流式输出异常，已补充规则版报告建议。\n"
        for chunk in _chunk_text(missing, 80):
            yield {"type": "chunk", "content": chunk}
    yield {"type": "done", "mode": "fallback"}


def _build_ai_report_prompt(report_context: Dict[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "你是资深高校职业规划顾问与生涯发展教练，请基于结构化数据输出可执行、可解释的Markdown职业规划报告。"
        "报告目标以“长期职业发展决策”与“阶段能力建设路径”为核心，求职内容只作为阶段任务，不可喧宾夺主。"
        "请纳入职业规划工具: MBTI、霍兰德、能力素质冰山模型；若输入已提供结果，必须直接使用，不得要求重复测评。"
        "必须按学生阶段给建议：大一大二以课程项目、竞赛、社团/实验室实践为主，不得将实习作为硬性要求；"
        "大三大四可将实习作为可选强化项。"
        "严禁自相矛盾：同一能力维度不能同时写‘优势明显’和‘短板严重’。"
    )
    user_prompt = (
        "请严格使用Markdown格式输出中文报告，必须包含以下章节:\n"
        "1. 学生就业能力画像\n"
        "2. 职业探索与人岗匹配（含4维评分解释）\n"
        "3. 职业生涯规划工具结果（MBTI/霍兰德/冰山模型）\n"
        "4. 岗位关联图谱与发展路径（垂直+换岗）\n"
        "5. 双线职业目标与分阶段行动计划（以职业规划主线为主，求职推进为辅）\n"
        "6. 风险提示与动态调整机制\n"
        "注意：不要在报告正文中输出 mermaid 代码块或雷达图，它们将由前端单独渲染。\n"
        "请优先读取student_profile中的academic_stage与academic_stage_label字段，并据此分层给建议。\n"
        "风险判定规则(必须遵守): 分数>=70判定为优势，40-69判定为待提升，<40判定为风险；"
        "若已判定为优势，不得再写该维度‘明显短板’。\n"
        "要求: 结论明确、建议可执行、避免空话，长度1200-2200字。\n"
        "额外要求:\n"
        "- 行动计划必须给出时间锚点（本月/本学期/6-12个月）与阶段产出物（作品、证书、项目、复盘文档）。\n"
        "- 给出至少2条职业路径比较（如深耕技术 vs 复合转型），并写明选择条件。\n"
        "- 给出动态校准机制：触发条件、观察指标、调整动作。\n"
        "- 避免把报告写成纯求职技巧清单，重点是职业定位与长期成长策略。\n"
        "以下是结构化输入数据:\n"
        f"{report_context}"
    )
    return system_prompt, user_prompt


def _chunk_text(text: str, size: int) -> List[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def _render_markdown_to_html(content: str) -> str:
    """将 Markdown 渲染为 HTML 用以在线预览"""
    try:
        md_module = importlib.import_module("markdown")
    except Exception:
        return ""

    body_html = md_module.markdown(
        content,
        extensions=["extra", "tables", "toc"],
    )

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>职业规划报告</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 40px 20px; background: #f8f9fa; }}
        .report-content {{ background: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 0; }}
        h2 {{ color: #2980b9; border-left: 4px solid #3498db; padding-left: 15px; margin-top: 30px; }}
        h3 {{ color: #34495e; margin-top: 25px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f2f2f2; font-weight: bold; }}
        tr:nth-child(even) {{ background-color: #fafafa; }}
        code {{ background-color: #f0f0f0; padding: 2px 4px; border-radius: 4px; font-family: Consolas, monospace; }}
        pre {{ background-color: #f0f0f0; padding: 15px; border-radius: 4px; overflow-x: auto; }}
        ul, ol {{ padding-left: 20px; }}
        li {{ margin-bottom: 8px; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 30px; }}
    </style>
</head>
<body>
    <div class="report-content">
        {body_html}
    </div>
</body>
</html>
"""
    return full_html


def export_report(markdown_text: str, output_dir: Path, stem: str) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem_safe = "".join(ch for ch in stem if ch.isalnum() or ch in ("_", "-")) or "career_report"
    pdf_path = output_dir / f"{stem_safe}.pdf"
    html_path = output_dir / f"{stem_safe}.html"

    result: Dict[str, str] = {}
    try:
        _export_pdf(markdown_text, pdf_path)
        result["pdf"] = pdf_path.name
    except Exception as exc:
        result["pdf_error"] = str(exc)

    try:
        html_content = _render_markdown_to_html(markdown_text)
        if html_content:
            html_path.write_text(html_content, encoding="utf-8")
            result["html"] = html_path.name
    except Exception as exc:
        result["html_error"] = str(exc)

    return result


def _export_pdf(text: str, pdf_path: Path) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, String
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("缺少 reportlab 依赖，请先安装: pip install reportlab") from exc

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ZhTitle",
        parent=styles["Heading1"],
        fontName="STSong-Light",
        fontSize=18,
        leading=24,
    )
    section_style = ParagraphStyle(
        "ZhSection",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=13,
        leading=18,
    )
    sub_style = ParagraphStyle(
        "ZhSubSection",
        parent=styles["Heading3"],
        fontName="STSong-Light",
        fontSize=11,
        leading=15,
    )
    body_style = ParagraphStyle(
        "ZhBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10.5,
        leading=16,
        wordWrap="CJK",
    )
    table_header_style = ParagraphStyle(
        "ZhTableHeader",
        parent=body_style,
        fontName="STSong-Light",
        fontSize=9,
        leading=12,
        alignment=1,
    )
    table_cell_style = ParagraphStyle(
        "ZhTableCell",
        parent=body_style,
        fontName="STSong-Light",
        fontSize=8.8,
        leading=11,
        wordWrap="CJK",
    )

    story: List[Any] = []
    lines = text.splitlines()
    idx = 0

    while idx < len(lines):
        raw = lines[idx]
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 2.5 * mm))
            idx += 1
            continue

        if stripped.startswith("# "):
            story.append(Paragraph(_md_inline_to_pdf(stripped[2:]), title_style))
            story.append(Spacer(1, 2 * mm))
            idx += 1
            continue

        if stripped.startswith("## "):
            story.append(Paragraph(_md_inline_to_pdf(stripped[3:]), section_style))
            idx += 1
            continue

        if stripped.startswith("### "):
            story.append(Paragraph(_md_inline_to_pdf(stripped[4:]), sub_style))
            idx += 1
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            content = stripped[2:].strip()
            story.append(Paragraph(f"• {_md_inline_to_pdf(content)}", body_style))
            idx += 1
            continue

        if stripped.startswith("```"):
            fence_lang = stripped[3:].strip().lower()
            idx += 1
            block_lines: List[str] = []
            while idx < len(lines) and not lines[idx].strip().startswith("```"):
                block_lines.append(lines[idx].rstrip())
                idx += 1
            if idx < len(lines) and lines[idx].strip().startswith("```"):
                idx += 1

            radar_model = _parse_mermaid_radar_block(block_lines) if fence_lang == "mermaid" else None
            if radar_model:
                if radar_model.get("title"):
                    story.append(Paragraph(_md_inline_to_pdf(str(radar_model.get("title", ""))), sub_style))
                story.append(_build_radar_pdf_drawing(radar_model, width=180 * mm, height=110 * mm))
                story.append(Spacer(1, 3 * mm))
                continue

            # 非 radar 图或无法解析时，退化为文本块展示，避免输出围栏符号。
            if block_lines:
                story.append(Paragraph(_md_inline_to_pdf("\n".join(block_lines)), body_style))
                story.append(Spacer(1, 2 * mm))
            continue

        if stripped.startswith("|"):
            table_lines = []
            while idx < len(lines) and lines[idx].strip().startswith("|"):
                table_lines.append(lines[idx].strip())
                idx += 1

            table_rows = _parse_md_table(table_lines)
            if table_rows:
                header = [Paragraph(_md_inline_to_pdf(c), table_header_style) for c in table_rows[0]]
                body = [
                    [Paragraph(_md_inline_to_pdf(c), table_cell_style) for c in row]
                    for row in table_rows[1:]
                ]
                table_data = [header] + body

                col_count = max(1, len(table_rows[0]))
                col_width = 180 * mm / col_count
                tbl = Table(table_data, repeatRows=1, colWidths=[col_width] * col_count)
                tbl.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EEF5")),
                            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B5C0CF")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 3),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ]
                    )
                )
                story.append(tbl)
                story.append(Spacer(1, 2 * mm))
            continue

        story.append(Paragraph(_md_inline_to_pdf(stripped), body_style))
        idx += 1

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="职业规划报告",
    )
    doc.build(story)


def _parse_md_table(table_lines: List[str]) -> List[List[str]]:
    rows: List[List[str]] = []
    for i, line in enumerate(table_lines):
        parts = [p.strip() for p in line.strip("|").split("|")]
        if i == 1 and parts and all(set(p) <= {":", "-"} for p in parts):
            continue
        rows.append(parts)

    if not rows:
        return []

    col_count = len(rows[0])
    normalized = []
    for row in rows:
        if len(row) < col_count:
            row = row + [""] * (col_count - len(row))
        elif len(row) > col_count:
            row = row[:col_count]
        normalized.append(row)
    return normalized


def _sanitize_for_pdf_text(text: str) -> str:
    raw = str(text or "")
    # 先把 HTML 换行标签归一为真实换行，便于后续在 PDF 中按回车显示。
    raw = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", raw)
    raw = re.sub(r"(?i)&lt;\s*br\s*/?\s*&gt;", "\n", raw)

    cleaned = []
    for ch in raw:
        cp = ord(ch)
        if 0x1F000 <= cp <= 0x1FAFF:
            continue
        if 0xFE00 <= cp <= 0xFE0F:
            continue
        if cp in (0x200B, 0x200C, 0x200D):
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("C") and ch not in ("\n", "\t", "\r"):
            continue
        cleaned.append(ch)

    normalized = "".join(cleaned)
    normalized = normalized.replace("•", "-")
    normalized = normalized.replace("→", "->")
    normalized = normalized.replace("·", "-")
    return normalized


def _md_inline_to_pdf(text: str) -> str:
    safe = html.escape(_sanitize_for_pdf_text(text))
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"__(.+?)__", r"<b>\1</b>", safe)
    safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", safe)
    safe = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", safe)
    safe = re.sub(r"`([^`]+)`", r"「\1」", safe)
    # ReportLab Paragraph 使用 <br/> 作为换行标记。
    safe = safe.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")
    return safe


def _parse_mermaid_radar_block(lines: List[str]) -> Dict[str, Any] | None:
    raw_lines = [str(x or "").strip() for x in lines if str(x or "").strip()]
    if not raw_lines:
        return None

    normalized_lines = [
        line.replace("“", '"').replace("”", '"').replace("：", ":").replace("，", ",")
        for line in raw_lines
    ]

    if not normalized_lines[0].lower().startswith("radar-beta"):
        return None

    title = "就业能力雷达图"
    axis_labels: List[str] = []
    min_value = 0.0
    max_value = 100.0
    datasets: List[Dict[str, Any]] = []

    for line in normalized_lines[1:]:
        title_match = re.match(r"^title\s+(.+)$", line, flags=re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip().strip('"') or title
            continue

        axis_match = re.match(
            r"^axis\s+\"?([^\"\[]+?)\"?\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]$",
            line,
            flags=re.IGNORECASE,
        )
        if axis_match:
            axis_labels.append(axis_match.group(1).strip())
            min_value = float(axis_match.group(2))
            max_value = float(axis_match.group(3))
            continue

        ds_match = re.match(r"^\"?([^\":]+?)\"?\s*:\s*\[\s*([^\]]+)\s*\]$", line)
        if ds_match:
            values = []
            for token in ds_match.group(2).split(","):
                token = token.strip()
                if not token:
                    continue
                try:
                    values.append(float(token))
                except ValueError:
                    pass
            if values:
                datasets.append({"name": ds_match.group(1).strip(), "values": values})

    if len(axis_labels) < 3 or not datasets:
        return None

    axis_count = len(axis_labels)
    fixed_sets: List[Dict[str, Any]] = []
    for ds in datasets[:4]:
        vals = list(ds["values"])[:axis_count]
        while len(vals) < axis_count:
            vals.append(min_value)
        fixed_sets.append({"name": ds["name"], "values": vals})

    if max_value <= min_value:
        max_value = min_value + 100.0

    return {
        "title": title,
        "axis_labels": axis_labels,
        "min_value": min_value,
        "max_value": max_value,
        "datasets": fixed_sets,
    }


def _build_radar_pdf_drawing(model: Dict[str, Any], width: float, height: float):
    from reportlab.lib import colors
    from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, String

    labels = model.get("axis_labels") or []
    datasets = model.get("datasets") or []
    if not labels or not datasets:
        d = Drawing(width, height)
        d.add(String(6, height - 16, "雷达图数据为空", fontName="Helvetica", fontSize=9, fillColor=colors.HexColor("#475569")))
        return d

    min_value = float(model.get("min_value", 0.0))
    max_value = float(model.get("max_value", 100.0))
    span = max(1e-9, max_value - min_value)

    d = Drawing(width, height)
    center_x = width * 0.36
    center_y = height * 0.5
    radius = min(width, height) * 0.33
    level_count = 5

    angles = [math.pi / 2 - (2 * math.pi * i / len(labels)) for i in range(len(labels))]

    for lv in range(1, level_count + 1):
        r = radius * lv / level_count
        pts: List[float] = []
        for ang in angles:
            pts.extend([center_x + r * math.cos(ang), center_y + r * math.sin(ang)])
        d.add(Polygon(points=pts, strokeColor=colors.HexColor("#D6DFEA"), strokeWidth=0.4, fillColor=None))

    for idx, ang in enumerate(angles):
        x = center_x + radius * math.cos(ang)
        y = center_y + radius * math.sin(ang)
        d.add(Line(center_x, center_y, x, y, strokeColor=colors.HexColor("#C5D0DD"), strokeWidth=0.45))

        lx = center_x + (radius + 12) * math.cos(ang)
        ly = center_y + (radius + 12) * math.sin(ang)
        d.add(String(lx, ly, str(labels[idx]), fontName="Helvetica", fontSize=7.6, fillColor=colors.HexColor("#334155")))

    palette = [
        colors.HexColor("#0EA5E9"),
        colors.HexColor("#10B981"),
        colors.HexColor("#F59E0B"),
        colors.HexColor("#EF4444"),
    ]

    legend_x = width * 0.7
    legend_y = height * 0.78

    for ds_idx, ds in enumerate(datasets):
        c = palette[ds_idx % len(palette)]
        pts: List[float] = []
        for i, val in enumerate(ds.get("values") or []):
            norm = (float(val) - min_value) / span
            norm = max(0.0, min(1.0, norm))
            r = radius * norm
            ang = angles[i]
            x = center_x + r * math.cos(ang)
            y = center_y + r * math.sin(ang)
            pts.extend([x, y])
            d.add(Circle(x, y, 1.8, strokeColor=c, fillColor=c))

        d.add(Polygon(points=pts, strokeColor=c, strokeWidth=1.0, fillColor=None))

        ly = legend_y - ds_idx * 13
        d.add(Line(legend_x, ly, legend_x + 12, ly, strokeColor=c, strokeWidth=1.5))
        d.add(String(legend_x + 16, ly - 3, str(ds.get("name", f"序列{ds_idx + 1}")), fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#334155")))

    d.add(String(width * 0.68, 8, f"刻度范围: {min_value:g} - {max_value:g}", fontName="Helvetica", fontSize=7.4, fillColor=colors.HexColor("#64748B")))
    return d
