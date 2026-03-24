from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Dict, List, Tuple

import pandas as pd

COLUMN_ALIASES: Dict[str, List[str]] = {
    "job_title": ["职位名称", "岗位名称", "职位", "job_title"],
    "city": ["工作地址", "工作城市", "城市", "city"],
    "salary": ["薪资范围", "薪资", "工资", "salary"],
    "company": ["公司全称", "公司名称", "企业名称", "company"],
    "industry": ["所属行业", "行业", "industry"],
    "company_size": ["人员规模", "规模", "company_size"],
    "company_type": ["企业性质", "企业类型", "company_type"],
    "job_code": ["职位编码", "岗位编码", "job_code"],
    "description": ["职位描述", "岗位描述", "职责描述", "description"],
    "company_desc": ["公司简介", "企业简介", "company_desc"],
}

SCRAPER_JSON_FIELD_MAP: Dict[str, str] = {
    "job_name": "job_title",
    "city_name": "city",
    "salary_desc": "salary",
    "company_name": "company",
    "industry": "industry",
    "company_scale": "company_size",
    "job_id": "job_code",
    "job_description": "description",
}


def _guess_column(df: pd.DataFrame, aliases: List[str]) -> str:
    for alias in aliases:
        if alias in df.columns:
            return alias
    return ""


def _normalize_jobs_df(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: Dict[str, str] = {}
    for normalized_name, aliases in COLUMN_ALIASES.items():
        source_name = _guess_column(df, aliases)
        if source_name:
            rename_map[source_name] = normalized_name

    df = df.rename(columns=rename_map)

    expected_columns = list(COLUMN_ALIASES.keys())
    for col in expected_columns:
        if col not in df.columns:
            df[col] = ""

    df = df[expected_columns].copy()
    for col in expected_columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df[df["job_title"] != ""].reset_index(drop=True)


def _from_scraper_json_df(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: Dict[str, str] = {}
    for source_col, normalized_col in SCRAPER_JSON_FIELD_MAP.items():
        if source_col in df.columns:
            rename_map[source_col] = normalized_col

    df = df.rename(columns=rename_map)

    expected_columns = list(COLUMN_ALIASES.keys())
    for col in expected_columns:
        if col not in df.columns:
            df[col] = ""

    df = df[expected_columns].copy()
    for col in expected_columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df[df["job_title"] != ""].reset_index(drop=True)


def _looks_like_scraper_json(df: pd.DataFrame) -> bool:
    required = {"job_name", "salary_desc", "city_name", "job_description"}
    return required.issubset(set(df.columns))


def locate_sqlite_dataset(data_dir: Path) -> Path | None:
    candidates = (
        sorted(data_dir.glob("*.db"))
        + sorted(data_dir.glob("*.sqlite"))
        + sorted(data_dir.glob("*.sqlite3"))
    )
    if not candidates:
        return None

    preferred = [p for p in candidates if p.stem.lower() in {"jobs", "career_jobs", "job_data"}]
    return preferred[0] if preferred else candidates[0]


def _pick_sqlite_table(conn: sqlite3.Connection) -> str:
    tables_df = pd.read_sql_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        conn,
    )
    tables = tables_df["name"].astype(str).tolist()
    if not tables:
        raise ValueError("SQLite 文件中没有可用的数据表")
    if "jobs" in tables:
        return "jobs"
    return tables[0]


def locate_dataset(data_dir: Path) -> Path:
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    candidates = sorted(data_dir.glob("*.xls")) + sorted(data_dir.glob("*.xlsx"))
    if not candidates:
        raise FileNotFoundError(f"No Excel dataset found in: {data_dir}")
    return candidates[0]


def locate_scraper_json_dataset(data_dir: Path) -> Path | None:
    if not data_dir.exists():
        return None

    candidates = sorted(data_dir.glob("jobs_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        candidates = sorted(data_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _load_jobs_from_json(json_path: Path) -> pd.DataFrame:
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"JSON 数据格式错误，期望列表: {json_path}")

    df = pd.DataFrame(raw)
    if _looks_like_scraper_json(df):
        return _from_scraper_json_df(df)
    return _normalize_jobs_df(df)


def convert_excel_to_sqlite(
    data_dir: Path,
    db_name: str = "jobs.db",
    table_name: str = "jobs",
) -> Tuple[Path, int]:
    dataset_path = locate_dataset(data_dir)
    df = pd.read_excel(dataset_path)
    jobs_df = _normalize_jobs_df(df)

    db_path = data_dir / db_name
    with sqlite3.connect(db_path) as conn:
        jobs_df.to_sql(table_name, conn, if_exists="replace", index=False)

    return db_path, int(len(jobs_df))


def load_jobs_dataframe(data_dir: Path) -> Tuple[pd.DataFrame, Path]:
    sqlite_path = locate_sqlite_dataset(data_dir)
    if sqlite_path and sqlite_path.exists():
        with sqlite3.connect(sqlite_path) as conn:
            table_name = _pick_sqlite_table(conn)
            df = pd.read_sql_query(f"SELECT * FROM [{table_name}]", conn)
        return _normalize_jobs_df(df), sqlite_path

    json_path = locate_scraper_json_dataset(data_dir)
    if json_path and json_path.exists():
        return _load_jobs_from_json(json_path), json_path

    dataset_path = locate_dataset(data_dir)
    df = pd.read_excel(dataset_path)
    return _normalize_jobs_df(df), dataset_path
