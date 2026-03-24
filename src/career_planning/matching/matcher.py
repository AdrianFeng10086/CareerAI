from __future__ import annotations

import re
from typing import Any, Dict, List


SKILL_ALIASES = {
    "java": ["java", "j2ee"],
    "python": ["python"],
    "sql": ["sql", "mysql", "postgresql", "oracle", "数据库"],
    "docker": ["docker", "容器"],
    "spring": ["spring", "springboot", "springcloud", "spring cloud"],
    "mybatis": ["mybatis", "mybatisplus", "mybatis-plus"],
    "mq": ["mq", "kafka", "rabbitmq", "rocketmq", "消息队列"],
    "jvm": ["jvm", "juc"],
    "redis": ["redis"],
    "测试": ["测试", "test", "qa", "自动化测试"],
    "算法": ["算法", "algorithm"],
}


def _norm_skill(text: str) -> str:
    s = str(text or "").strip().lower()
    s = re.sub(r"[\s\-_/+]+", "", s)
    return s


def _canonical_skill(text: str) -> str:
    n = _norm_skill(text)
    if not n:
        return ""
    for canon, alias_list in SKILL_ALIASES.items():
        for alias in alias_list:
            if _norm_skill(alias) in n or n in _norm_skill(alias):
                return canon
    return n


def _skill_overlap(student_skills: List[str], job_skills: List[str]) -> tuple[int, int]:
    if not job_skills:
        return (0, 0)

    s_set = {_canonical_skill(s) for s in student_skills if _canonical_skill(s)}
    j_set = {_canonical_skill(j) for j in job_skills if _canonical_skill(j)}

    overlap = len(s_set & j_set)
    return overlap, len(j_set)


def _skill_match(student_skills: List[str], job_skills: List[str]) -> float:
    overlap, total = _skill_overlap(student_skills, job_skills)
    if total <= 0:
        return 0.25
    return min(1.0, overlap / max(1, total))


def _role_affinity(intention: str, job_title: str) -> float:
    intention_norm = str(intention or "").lower().strip()
    job_norm = str(job_title or "").lower().strip()
    if not intention_norm:
        return 0.5
    if intention_norm in job_norm or job_norm in intention_norm:
        return 1.0

    i_tokens = [t for t in re.split(r"[\s,，/、-]+", intention_norm) if len(t) >= 2]
    j_tokens = [t for t in re.split(r"[\s,，/、-]+", job_norm) if len(t) >= 2]
    if not i_tokens or not j_tokens:
        return 0.2
    overlap = len(set(i_tokens) & set(j_tokens))
    return min(1.0, overlap / max(1, len(set(i_tokens))))


def _city_affinity(target_city: str, job_cities: List[str]) -> float:
    city = str(target_city or "").strip()
    if not city:
        return 0.6
    return 1.0 if any(city in c or c in city for c in job_cities) else 0.1


def _salary_affinity(expected_k: int, job_avg_k: float) -> float:
    if expected_k <= 0 or job_avg_k <= 0:
        return 0.6
    diff = abs(expected_k - job_avg_k)
    if diff <= 2:
        return 1.0
    if diff <= 5:
        return 0.8
    if diff <= 8:
        return 0.6
    return 0.3


def match_jobs(student_profile: Dict[str, Any], job_profiles: List[Dict[str, Any]], top_k: int = 8) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for job in job_profiles:
        role_affinity = _role_affinity(student_profile.get("employment_intention", ""), job.get("job_title", ""))
        city_affinity = _city_affinity(student_profile.get("target_city", ""), job.get("top_cities", []))
        salary_affinity = _salary_affinity(int(student_profile.get("expected_salary_k", 0) or 0), float(job.get("avg_salary_k", 0) or 0))
        skill_overlap_count, job_skill_count = _skill_overlap(
            student_profile.get("skills", []),
            job.get("core_hard_skills", []),
        )

        foundation = min(
            1.0,
            0.35 * (len(student_profile.get("certificates", [])) / 3)
            + 0.25 * student_profile.get("internship_ability", 0)
            + 0.15 * role_affinity
            + 0.15 * city_affinity
            + 0.15 * salary_affinity,
        )

        professional_skills = min(
            1.0,
            0.75 * _skill_match(student_profile.get("skills", []), job.get("core_hard_skills", []))
            + 0.25 * role_affinity,
        )

        quality_gap = (
            abs(student_profile.get("communication_ability", 0) - job.get("communication_ability", 0.6))
            + abs(student_profile.get("stress_tolerance", 0) - job.get("stress_tolerance", 0.6))
            + abs(student_profile.get("learning_ability", 0) - job.get("learning_ability", 0.6))
        ) / 3
        professional_quality = max(0.0, 1.0 - quality_gap)

        potential = min(
            1.0,
            0.5 * student_profile.get("innovation_ability", 0)
            + 0.3 * student_profile.get("learning_ability", 0)
            + 0.2 * role_affinity,
        )

        score = (
            0.22 * foundation
            + 0.43 * professional_skills
            + 0.2 * professional_quality
            + 0.15 * potential
        )

        gaps = sorted(list(set(job.get("core_hard_skills", [])) - set(student_profile.get("skills", []))))[:6]

        results.append(
            {
                "job_title": job["job_title"],
                "score_raw": round(score * 100, 2),
                "score": round(score * 100, 1),
                "dimension_scores": {
                    "foundation_requirements": round(foundation * 100, 1),
                    "professional_skills": round(professional_skills * 100, 1),
                    "professional_quality": round(professional_quality * 100, 1),
                    "development_potential": round(potential * 100, 1),
                },
                "advantage_skills": sorted(list(set(student_profile.get("skills", [])) & set(job.get("core_hard_skills", []))))[:6],
                "gap_skills": gaps,
                "debug_factors": {
                    "role_affinity": round(role_affinity, 4),
                    "city_affinity": round(city_affinity, 4),
                    "salary_affinity": round(salary_affinity, 4),
                    "skill_overlap_count": skill_overlap_count,
                    "job_skill_count": job_skill_count,
                    "job_sample_size": int(job.get("sample_size", 0) or 0),
                },
                "weighting": {
                    "foundation_requirements": 0.22,
                    "professional_skills": 0.43,
                    "professional_quality": 0.2,
                    "development_potential": 0.15,
                },
            }
        )

    # Multi-key sorting to avoid fixed Top5 under score ties.
    results.sort(
        key=lambda x: (
            x.get("score_raw", 0),
            x.get("debug_factors", {}).get("role_affinity", 0),
            x.get("debug_factors", {}).get("skill_overlap_count", 0),
            x.get("debug_factors", {}).get("city_affinity", 0),
            -len(x.get("gap_skills", [])),
            x.get("debug_factors", {}).get("job_sample_size", 0),
        ),
        reverse=True,
    )
    return results[:top_k]
