from __future__ import annotations

import json
from pathlib import Path
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
    "url": ["招聘链接", "职位链接", "岗位链接", "网址", "url"],
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
    "job_href": "url",
    "job_url": "url",
    "url": "url",
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


def locate_vector_dataset(data_dir: Path) -> Path | None:
    candidate = data_dir / "career_jobs_vector_db"
    return candidate if candidate.exists() and candidate.is_dir() else None


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


def _load_jobs_from_vector_store(data_dir: Path) -> pd.DataFrame:
    try:
        from src.career_job_store import load_all_jobs_from_vector_store
    except Exception:
        from career_job_store import load_all_jobs_from_vector_store

    rows = load_all_jobs_from_vector_store(data_dir, limit=50000)
    if not rows:
        raise ValueError("向量数据库中暂无岗位数据")

    df = pd.DataFrame(rows)
    return _from_scraper_json_df(df)


def convert_excel_to_sqlite(
    data_dir: Path,
    db_name: str = "jobs.db",
    table_name: str = "jobs",
) -> Tuple[Path, int]:
    # Backward compatibility: keep function name, but export as JSON dataset.
    del table_name
    dataset_path = locate_dataset(data_dir)
    df = pd.read_excel(dataset_path)
    jobs_df = _normalize_jobs_df(df)

    output_name = Path(db_name).with_suffix(".json").name
    out_path = data_dir / output_name
    jobs_df.to_json(out_path, orient="records", force_ascii=False)

    return out_path, int(len(jobs_df))


def load_jobs_dataframe(data_dir: Path) -> pd.DataFrame:
    vector_path = locate_vector_dataset(data_dir)
    if vector_path:
        try:
            return _load_jobs_from_vector_store(data_dir)
        except Exception:
            pass

    json_path = locate_scraper_json_dataset(data_dir)
    if json_path and json_path.exists():
        return _load_jobs_from_json(json_path)

    dataset_path = locate_dataset(data_dir)
    df = pd.read_excel(dataset_path)
    return _normalize_jobs_df(df)
