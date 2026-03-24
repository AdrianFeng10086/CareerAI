"""
职业规划岗位数据 SQLite 存储服务。

设计目标:
1. 爬取后异步入库，不阻塞前台任务。
2. 与历史数据比对去重后写入。
3. 作为职业规划模块的稳定数据源。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

DB_NAME = "career_jobs.db"
TABLE_NAME = "jobs"

_DB_LOCK = threading.Lock()


def _compute_dedup_key(job: Dict[str, Any]) -> str:
    job_id = str(job.get("job_id", "")).strip()
    if job_id:
        return f"job_id:{job_id}"

    parts = [
        str(job.get("job_name", "")).strip(),
        str(job.get("company_name", "")).strip(),
        str(job.get("city_name", "")).strip(),
        str(job.get("salary_desc", "")).strip(),
    ]
    return "fallback:" + "|".join(parts)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dedup_key TEXT NOT NULL UNIQUE,
            job_id TEXT,
            job_name TEXT,
            salary_desc TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            salary_months INTEGER,
            city_name TEXT,
            area_district TEXT,
            business_district TEXT,
            experience TEXT,
            education TEXT,
            job_type TEXT,
            skills_json TEXT,
            job_labels_json TEXT,
            company_name TEXT,
            company_scale TEXT,
            industry TEXT,
            security_id TEXT,
            encrypt_boss_id TEXT,
            encrypt_brand_id TEXT,
            boss_name TEXT,
            boss_title TEXT,
            job_description TEXT,
            address TEXT,
            scraped_at TEXT,
            inserted_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_job_name ON {TABLE_NAME}(job_name)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_city_name ON {TABLE_NAME}(city_name)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_industry ON {TABLE_NAME}(industry)"
    )


def upsert_jobs_to_sqlite(jobs_data: List[Dict[str, Any]], data_dir: Path) -> Dict[str, int]:
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / DB_NAME

    inserted = 0
    duplicated = 0

    with _DB_LOCK:
        conn = sqlite3.connect(db_path)
        try:
            _ensure_schema(conn)
            now = datetime.now().isoformat()

            sql = f"""
            INSERT OR IGNORE INTO {TABLE_NAME} (
                dedup_key,
                job_id,
                job_name,
                salary_desc,
                salary_min,
                salary_max,
                salary_months,
                city_name,
                area_district,
                business_district,
                experience,
                education,
                job_type,
                skills_json,
                job_labels_json,
                company_name,
                company_scale,
                industry,
                security_id,
                encrypt_boss_id,
                encrypt_brand_id,
                boss_name,
                boss_title,
                job_description,
                address,
                scraped_at,
                inserted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            for job in jobs_data:
                dedup_key = _compute_dedup_key(job)
                before_changes = conn.total_changes
                conn.execute(
                    sql,
                    (
                        dedup_key,
                        str(job.get("job_id", "") or ""),
                        str(job.get("job_name", "") or ""),
                        str(job.get("salary_desc", "") or ""),
                        int(job.get("salary_min", 0) or 0),
                        int(job.get("salary_max", 0) or 0),
                        int(job.get("salary_months", 0) or 0),
                        str(job.get("city_name", "") or ""),
                        str(job.get("area_district", "") or ""),
                        str(job.get("business_district", "") or ""),
                        str(job.get("experience", "") or ""),
                        str(job.get("education", "") or ""),
                        str(job.get("job_type", "") or ""),
                        json.dumps(job.get("skills", []) or [], ensure_ascii=False),
                        json.dumps(job.get("job_labels", []) or [], ensure_ascii=False),
                        str(job.get("company_name", "") or ""),
                        str(job.get("company_scale", "") or ""),
                        str(job.get("industry", "") or ""),
                        str(job.get("security_id", "") or ""),
                        str(job.get("encrypt_boss_id", "") or ""),
                        str(job.get("encrypt_brand_id", "") or ""),
                        str(job.get("boss_name", "") or ""),
                        str(job.get("boss_title", "") or ""),
                        str(job.get("job_description", "") or ""),
                        str(job.get("address", "") or ""),
                        str(job.get("scraped_at", "") or ""),
                        now,
                    ),
                )
                if conn.total_changes > before_changes:
                    inserted += 1
                else:
                    duplicated += 1

            conn.commit()
        finally:
            conn.close()

    return {
        "total": len(jobs_data),
        "inserted": inserted,
        "duplicated": duplicated,
    }


def schedule_upsert_jobs_to_sqlite(jobs_data: List[Dict[str, Any]], data_dir: Path) -> threading.Thread:
    # 复制一份数据，避免调用方后续修改对象导致后台线程读取不一致。
    payload = [dict(item) for item in jobs_data]

    def _worker() -> None:
        try:
            upsert_jobs_to_sqlite(payload, data_dir)
        except Exception:
            # 后台任务失败不影响前台业务。
            return

    thread = threading.Thread(target=_worker, daemon=True, name="career-sqlite-upsert")
    thread.start()
    return thread
