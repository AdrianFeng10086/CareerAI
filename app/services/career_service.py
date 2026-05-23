"""职业规划相关业务逻辑桥接 src/career_planning。"""

from __future__ import annotations

import shutil
from pathlib import Path

from flask import current_app

from app.services.auth_service import get_user_output_dir
from app.services.intent_service import (
    extract_dialogue_rag_queries,
    extract_job_titles_from_rag_contexts,
)
from app.utils.llm_client import build_career_llm_client
from src.career_job_store import build_rag_contexts_for_queries
from src.career_planning.ai.ai_planner import generate_ai_matching_and_paths
from src.career_planning.data.data_loader import load_jobs_dataframe
from src.career_planning.matching.matcher import match_jobs
from src.career_planning.matching.profiles import build_job_profiles
from src.config import Config


def get_career_data_dir() -> Path:
    cfg = Config.load()
    base_dir: Path = current_app.config["BASE_DIR"]
    return base_dir / cfg.data_dir


def get_career_output_dir() -> Path:
    return get_user_output_dir()


def persist_career_jobs_dataset(source_path: str) -> str:
    source = Path(str(source_path or "")).resolve()
    if not source.exists() or not source.is_file():
        return ""

    cfg = Config.load()
    base_dir: Path = current_app.config["BASE_DIR"]
    data_dir = base_dir / cfg.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "career_jobs_latest.json"
    shutil.copyfile(source, target)
    return str(target)


def career_recommend_jobs_for_dialogue(student_text: str) -> list[str]:
    text = str(student_text or "").strip()
    if not text:
        return []

    try:
        rag_queries = extract_dialogue_rag_queries(text, max_queries=6)
        rag_contexts = build_rag_contexts_for_queries(
            data_dir=get_career_data_dir(),
            query_texts=rag_queries,
            city_name="",
            days=120,
            top_k=8,
        )
        rag_titles = extract_job_titles_from_rag_contexts(rag_contexts, limit=8)
        if rag_titles:
            return rag_titles
    except Exception:
        pass

    try:
        jobs_df = load_jobs_dataframe(get_career_data_dir())
        job_profiles = build_job_profiles(jobs_df)
        llm = build_career_llm_client()
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
