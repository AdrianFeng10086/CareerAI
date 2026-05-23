"""
求职模块专用 SQLite 缓存存储。

设计原则:
1. 仅服务求职检索缓存，不参与职业规划 RAG 检索。
2. 与向量库解耦，避免求职阶段受语义检索干扰。
3. 缓存窗口由外部传入起始时间（last_search_time）。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

DB_NAME = "job_search_cache.db"
TABLE_NAME = "job_search_jobs"

_DB_LOCK = threading.Lock()


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _parse_iso_to_ts(value: str) -> int:
    text = str(value or "").strip()
    if not text:
        return int(datetime.now().timestamp())
    try:
        return int(datetime.fromisoformat(text).timestamp())
    except Exception:
        return int(datetime.now().timestamp())


def _parse_json_list(value: Any) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        return []
    return []


def _compute_dedup_key(job: Dict[str, Any]) -> str:
    job_id = str(job.get("job_id", "") or "").strip()
    if job_id:
        return f"job_id:{job_id}"

    parts = [
        str(job.get("job_name", "") or "").strip(),
        str(job.get("company_name", "") or "").strip(),
        str(job.get("city_name", "") or "").strip(),
        str(job.get("salary_desc", "") or "").strip(),
    ]
    raw = "|".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"fallback:{digest}"


def _connect(data_dir: Path) -> sqlite3.Connection:
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(data_dir / DB_NAME))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            dedup_key TEXT PRIMARY KEY,
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
            job_description TEXT,
            url TEXT,
            address TEXT,
            scraped_at TEXT,
            inserted_at TEXT,
            inserted_ts INTEGER
        )
        """
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_city_ts ON {TABLE_NAME}(city_name, inserted_ts DESC)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_job_name ON {TABLE_NAME}(job_name)"
    )
    conn.commit()


def _row_from_job(job: Dict[str, Any], inserted_at: str) -> Dict[str, Any]:
    return {
        "dedup_key": _compute_dedup_key(job),
        "job_id": str(job.get("job_id", "") or ""),
        "job_name": str(job.get("job_name", "") or ""),
        "salary_desc": str(job.get("salary_desc", "") or ""),
        "salary_min": _safe_int(job.get("salary_min", 0)),
        "salary_max": _safe_int(job.get("salary_max", 0)),
        "salary_months": _safe_int(job.get("salary_months", 0)),
        "city_name": str(job.get("city_name", "") or ""),
        "area_district": str(job.get("area_district", "") or ""),
        "business_district": str(job.get("business_district", "") or ""),
        "experience": str(job.get("experience", "") or ""),
        "education": str(job.get("education", "") or ""),
        "job_type": str(job.get("job_type", "") or ""),
        "skills_json": json.dumps(job.get("skills", []) or [], ensure_ascii=False),
        "job_labels_json": json.dumps(job.get("job_labels", []) or [], ensure_ascii=False),
        "company_name": str(job.get("company_name", "") or ""),
        "company_scale": str(job.get("company_scale", "") or ""),
        "industry": str(job.get("industry", "") or ""),
        "job_description": str(job.get("job_description", "") or ""),
        "url": str(job.get("url", "") or ""),
        "address": str(job.get("address", "") or ""),
        "scraped_at": str(job.get("scraped_at", "") or ""),
        "inserted_at": inserted_at,
        "inserted_ts": _parse_iso_to_ts(inserted_at),
    }


def _iter_chunks(items: List[str], size: int = 200) -> Iterable[List[str]]:
    chunk_size = max(1, int(size))
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def upsert_jobs_to_search_store(jobs_data: List[Dict[str, Any]], data_dir: Path) -> Dict[str, int]:
    if not jobs_data:
        return {"total": 0, "inserted": 0, "duplicated": 0}

    now_iso = datetime.now().isoformat()
    rows = [_row_from_job(dict(item), now_iso) for item in jobs_data]
    rows = [x for x in rows if x.get("dedup_key")]
    if not rows:
        return {"total": len(jobs_data), "inserted": 0, "duplicated": len(jobs_data)}

    with _DB_LOCK:
        conn = _connect(data_dir)
        try:
            _ensure_table(conn)

            dedup_keys = [str(x["dedup_key"]) for x in rows]
            existing: set[str] = set()
            for chunk in _iter_chunks(dedup_keys):
                placeholders = ",".join(["?"] * len(chunk))
                sql = f"SELECT dedup_key FROM {TABLE_NAME} WHERE dedup_key IN ({placeholders})"
                existing_rows = conn.execute(sql, chunk).fetchall()
                existing.update(str(r[0]) for r in existing_rows)

            conn.executemany(
                f"""
                INSERT INTO {TABLE_NAME} (
                    dedup_key, job_id, job_name, salary_desc, salary_min, salary_max, salary_months,
                    city_name, area_district, business_district, experience, education, job_type,
                    skills_json, job_labels_json, company_name, company_scale, industry,
                    job_description, url, address, scraped_at, inserted_at, inserted_ts
                ) VALUES (
                    :dedup_key, :job_id, :job_name, :salary_desc, :salary_min, :salary_max, :salary_months,
                    :city_name, :area_district, :business_district, :experience, :education, :job_type,
                    :skills_json, :job_labels_json, :company_name, :company_scale, :industry,
                    :job_description, :url, :address, :scraped_at, :inserted_at, :inserted_ts
                )
                ON CONFLICT(dedup_key) DO UPDATE SET
                    job_id=excluded.job_id,
                    job_name=excluded.job_name,
                    salary_desc=excluded.salary_desc,
                    salary_min=excluded.salary_min,
                    salary_max=excluded.salary_max,
                    salary_months=excluded.salary_months,
                    city_name=excluded.city_name,
                    area_district=excluded.area_district,
                    business_district=excluded.business_district,
                    experience=excluded.experience,
                    education=excluded.education,
                    job_type=excluded.job_type,
                    skills_json=excluded.skills_json,
                    job_labels_json=excluded.job_labels_json,
                    company_name=excluded.company_name,
                    company_scale=excluded.company_scale,
                    industry=excluded.industry,
                    job_description=excluded.job_description,
                    url=excluded.url,
                    address=excluded.address,
                    scraped_at=excluded.scraped_at,
                    inserted_at=excluded.inserted_at,
                    inserted_ts=excluded.inserted_ts
                """,
                rows,
            )
            conn.commit()

            inserted = sum(1 for x in rows if x["dedup_key"] not in existing)
            duplicated = len(rows) - inserted
            ignored = max(0, len(jobs_data) - len(rows))
            return {"total": len(jobs_data), "inserted": inserted, "duplicated": duplicated + ignored}
        finally:
            conn.close()


def schedule_upsert_jobs_to_search_store(jobs_data: List[Dict[str, Any]], data_dir: Path) -> threading.Thread:
    payload = [dict(item) for item in jobs_data]

    def _worker() -> None:
        try:
            upsert_jobs_to_search_store(payload, data_dir)
        except Exception:
            return

    thread = threading.Thread(target=_worker, daemon=True, name="job-search-sqlite-upsert")
    thread.start()
    return thread


def fetch_jobs_by_city_keyword_since(
    data_dir: Path,
    city_name: str,
    keyword: str,
    start_time_iso: str,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    city = str(city_name or "").strip()
    kw = str(keyword or "").strip()
    if not city or not kw:
        return []

    start_ts = _parse_iso_to_ts(start_time_iso)
    like_kw = f"%{kw}%"

    with _DB_LOCK:
        conn = _connect(data_dir)
        try:
            _ensure_table(conn)
            rows = conn.execute(
                f"""
                SELECT *
                FROM {TABLE_NAME}
                WHERE city_name = ?
                  AND inserted_ts >= ?
                  AND (
                    job_name LIKE ?
                    OR job_description LIKE ?
                    OR skills_json LIKE ?
                    OR company_name LIKE ?
                  )
                ORDER BY inserted_ts DESC
                LIMIT ?
                """,
                (city, start_ts, like_kw, like_kw, like_kw, like_kw, max(1, int(limit))),
            ).fetchall()
        finally:
            conn.close()

    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "job_id": str(row["job_id"] or ""),
                "job_name": str(row["job_name"] or ""),
                "salary_desc": str(row["salary_desc"] or ""),
                "salary_min": _safe_int(row["salary_min"]),
                "salary_max": _safe_int(row["salary_max"]),
                "salary_months": _safe_int(row["salary_months"]),
                "city_name": str(row["city_name"] or ""),
                "area_district": str(row["area_district"] or ""),
                "business_district": str(row["business_district"] or ""),
                "experience": str(row["experience"] or ""),
                "education": str(row["education"] or ""),
                "job_type": str(row["job_type"] or ""),
                "skills": _parse_json_list(row["skills_json"]),
                "job_labels": _parse_json_list(row["job_labels_json"]),
                "company_name": str(row["company_name"] or ""),
                "company_scale": str(row["company_scale"] or ""),
                "industry": str(row["industry"] or ""),
                "job_description": str(row["job_description"] or ""),
                "url": str(row["url"] or ""),
                "address": str(row["address"] or ""),
                "scraped_at": str(row["scraped_at"] or ""),
                "inserted_at": str(row["inserted_at"] or ""),
            }
        )

    return results


def purge_jobs_before_ts(data_dir: Path, threshold_ts: int) -> int:
    with _DB_LOCK:
        conn = _connect(data_dir)
        try:
            _ensure_table(conn)
            cursor = conn.execute(
                f"DELETE FROM {TABLE_NAME} WHERE inserted_ts < ?",
                (int(threshold_ts),),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
        finally:
            conn.close()
