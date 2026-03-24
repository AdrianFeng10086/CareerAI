from __future__ import annotations

from collections import Counter
import re
from typing import Any, Dict, List

import pandas as pd

HARD_SKILLS = [
    "Python", "Java", "C++", "SQL", "MySQL", "PostgreSQL", "Linux", "Git", "Docker",
    "Kubernetes", "TensorFlow", "PyTorch", "机器学习", "深度学习", "数据分析", "可视化",
    "NLP", "大模型", "Prompt", "RAG", "Agent", "前端", "Vue", "React", "Node", "后端",
    "Spring", "算法", "网络安全", "测试", "自动化测试", "云计算", "微服务",
]

SOFT_SKILLS = [
    "沟通", "表达", "团队协作", "抗压", "学习能力", "创新", "执行力", "责任心", "领导力",
    "问题解决", "逻辑思维", "跨部门协作", "自驱", "复盘", "项目管理",
]

CERT_TERMS = ["证书", "软考", "PMP", "CET", "计算机等级", "华为认证", "AWS", "阿里云", "ACP"]

STOP_WORDS = {
    "负责", "相关", "工作", "能力", "岗位", "职位", "要求", "进行", "具有", "熟悉", "掌握",
    "优先", "以上", "本科", "专科", "经验", "参与", "完成", "团队", "公司", "业务", "开发",
}


def _hit_terms(text: str, terms: List[str]) -> List[str]:
    lower = text.lower()
    hits: List[str] = []
    for term in terms:
        if term.lower() in lower:
            hits.append(term)
    return hits


def _salary_to_number(raw: str) -> float:
    text = str(raw or "").replace("K", "k")
    if "k" not in text:
        return 0.0
    parts = text.split("-")
    nums: List[float] = []
    for p in parts:
        seg = p.strip()
        if "k" in seg:
            try:
                nums.append(float(seg.split("k")[0]))
            except Exception:
                pass
    if not nums:
        return 0.0
    return sum(nums) / len(nums)


def _extract_fallback_skills(text: str, limit: int = 8) -> List[str]:
    terms = re.findall(r"[A-Za-z][A-Za-z0-9+#\./-]{1,20}", text)
    terms += re.findall(r"[\u4e00-\u9fa5]{2,8}", text)

    cleaned: List[str] = []
    for t in terms:
        token = t.strip()
        if len(token) < 2:
            continue
        if token in STOP_WORDS:
            continue
        cleaned.append(token)

    counter = Counter(cleaned)
    # 至少出现两次，避免噪音词影响。
    return [k for k, v in counter.most_common(20) if v >= 2][:limit]


def _role_requirement_scores(role: str, desc_text: str) -> Dict[str, float]:
    text = f"{role} {desc_text}".lower()
    learning = 0.62
    stress = 0.58
    communication = 0.58
    innovation = 0.55
    internship = 0.52

    if any(k in text for k in ["架构", "算法", "ai", "机器学习", "研发"]):
        innovation += 0.2
        learning += 0.18
    if any(k in text for k in ["实施", "运维", "交付", "支持", "值班"]):
        stress += 0.22
        communication += 0.1
    if any(k in text for k in ["产品", "项目", "经理", "对接", "客户"]):
        communication += 0.25
        stress += 0.08
    if any(k in text for k in ["应届", "校招", "实习"]):
        internship += 0.22

    return {
        "learning_ability": round(min(1.0, learning), 2),
        "stress_tolerance": round(min(1.0, stress), 2),
        "communication_ability": round(min(1.0, communication), 2),
        "innovation_ability": round(min(1.0, innovation), 2),
        "internship_preference": round(min(1.0, internship), 2),
    }


def build_job_profiles(df: pd.DataFrame, top_n: int | None = None) -> List[Dict[str, Any]]:
    df2 = df.copy()
    code_series = df2["job_code"].astype(str).str.strip()
    title_nunique = int(df2["job_title"].nunique())
    has_code_ratio = float((code_series != "").mean()) if len(df2) else 0.0

    # When title categories are too coarse (e.g. ~50), use code prefix buckets for finer profiles.
    use_code_bucket = title_nunique < 80 and has_code_ratio > 0.5

    profile_groups: List[tuple[str, int, pd.DataFrame]] = []
    if use_code_bucket:
        df2["_role_bucket"] = code_series.str[:4]
        bucket_part = df2[df2["_role_bucket"] != ""]
        bucket_counts = bucket_part["_role_bucket"].value_counts()
        if top_n and top_n > 0:
            bucket_counts = bucket_counts.head(top_n)
        for bucket, count in bucket_counts.items():
            part = bucket_part[bucket_part["_role_bucket"] == bucket]
            title = part["job_title"].value_counts().index.tolist()
            dominant_title = title[0] if title else "岗位"
            role_name = f"{dominant_title}({bucket})"
            profile_groups.append((role_name, int(count), part))
    else:
        role_counts = df2["job_title"].value_counts()
        if top_n and top_n > 0:
            role_counts = role_counts.head(top_n)
        for role, count in role_counts.items():
            part = df2[df2["job_title"] == role]
            profile_groups.append((str(role), int(count), part))

    profiles: List[Dict[str, Any]] = []

    for role, count, part in profile_groups:
        desc_text = " ".join(part["description"].tolist())
        salary_vals = [_salary_to_number(v) for v in part["salary"].tolist()]
        salary_vals = [v for v in salary_vals if v > 0]

        hard_skills = Counter(_hit_terms(desc_text, HARD_SKILLS)).most_common(8)
        soft_skills = Counter(_hit_terms(desc_text, SOFT_SKILLS)).most_common(6)
        certs = Counter(_hit_terms(desc_text, CERT_TERMS)).most_common(4)
        req_scores = _role_requirement_scores(role, desc_text)

        hard_skill_list = [x[0] for x in hard_skills]
        if len(hard_skill_list) < 4:
            fallback = _extract_fallback_skills(desc_text, limit=8)
            for item in fallback:
                if item not in hard_skill_list:
                    hard_skill_list.append(item)
                if len(hard_skill_list) >= 8:
                    break

        profile = {
            "job_title": role,
            "sample_size": int(count),
            "core_hard_skills": hard_skill_list,
            "core_soft_skills": [x[0] for x in soft_skills],
            "cert_requirements": [x[0] for x in certs],
            "learning_ability": req_scores["learning_ability"],
            "stress_tolerance": req_scores["stress_tolerance"],
            "communication_ability": req_scores["communication_ability"],
            "innovation_ability": req_scores["innovation_ability"],
            "internship_preference": req_scores["internship_preference"],
            "avg_salary_k": round(sum(salary_vals) / len(salary_vals), 2) if salary_vals else 0,
            "top_cities": part["city"].value_counts().head(3).index.tolist(),
            "top_industries": part["industry"].value_counts().head(3).index.tolist(),
        }
        profiles.append(profile)

    while len(profiles) < 10:
        idx = len(profiles) + 1
        profiles.append(
            {
                "job_title": f"岗位画像示例{idx}",
                "sample_size": 0,
                "core_hard_skills": ["Python", "SQL", "沟通"],
                "core_soft_skills": ["学习能力", "问题解决"],
                "cert_requirements": [],
                "learning_ability": 0.7,
                "stress_tolerance": 0.65,
                "communication_ability": 0.7,
                "innovation_ability": 0.65,
                "internship_preference": 0.6,
                "avg_salary_k": 0,
                "top_cities": [],
                "top_industries": [],
            }
        )

    return profiles


def build_vertical_graph(job_profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    graph: List[Dict[str, Any]] = []
    for profile in job_profiles[:10]:
        title = profile["job_title"]
        graph.append(
            {
                "job_title": title,
                "path": [f"初级{title}", title, f"资深{title}", f"{title}主管"],
                "description": f"{title} 的典型垂直晋升路径。",
            }
        )
    return graph


def build_transition_graph() -> List[Dict[str, Any]]:
    return [
        {"job_title": "数据分析师", "transitions": ["算法工程师", "BI产品经理", "数据产品经理"]},
        {"job_title": "前端工程师", "transitions": ["全栈工程师", "客户端工程师", "前端架构师"]},
        {"job_title": "后端工程师", "transitions": ["架构师", "SRE工程师", "技术经理"]},
        {"job_title": "测试工程师", "transitions": ["测试开发工程师", "质量负责人", "DevOps工程师"]},
        {"job_title": "AI算法工程师", "transitions": ["机器学习平台工程师", "AI产品经理", "研究工程师"]},
    ]


def build_related_edges(job_profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    for i in range(len(job_profiles)):
        for j in range(i + 1, len(job_profiles)):
            a = job_profiles[i]
            b = job_profiles[j]
            overlap = set(a["core_hard_skills"]) & set(b["core_hard_skills"])
            if len(overlap) >= 2:
                edges.append(
                    {
                        "source": a["job_title"],
                        "target": b["job_title"],
                        "relation": "skill_overlap",
                        "overlap_skills": sorted(list(overlap))[:5],
                    }
                )
    return edges
