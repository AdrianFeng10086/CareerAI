from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd

from career_job_store import upsert_jobs_to_vector_store

TABULAR_EXTENSIONS = {".csv", ".xls", ".xlsx"}

COLUMN_ALIASES: Dict[str, List[str]] = {
    "job_name": ["job_name", "job_title", "职位名称", "岗位名称", "职位"],
    "company_name": ["company_name", "company", "公司名称", "企业名称", "公司全称"],
    "city_name": ["city_name", "city", "工作城市", "工作地址", "城市", "area"],
    "salary_desc": ["salary_desc", "salary", "薪资", "薪资范围", "工资", "money"],
    "experience": ["experience", "经验要求", "工作经验", "job_exp"],
    "education": ["education", "学历要求", "学历", "job_deu"],
    "job_type": ["job_type", "岗位类型", "职位类型"],
    "industry": ["industry", "所属行业", "行业"],
    "company_scale": ["company_scale", "company_size", "人员规模", "规模"],
    "job_id": ["job_id", "job_code", "职位编码", "岗位编码"],
    "job_href": ["job_href", "职位链接", "url"],
    "job_description": ["job_description", "description", "职位描述", "岗位描述"],
    "job_labels": ["job_labels", "job_wel", "职位标签", "岗位标签"],
    "skills": ["skills", "skill", "技能", "技能要求"],
    "scraped_at": ["scraped_at", "date", "抓取时间", "发布时间", "更新时间"],
    "address": ["address", "详细地址", "办公地点"],
}


def locate_tabular_datasets(data_dir: Path) -> List[Path]:
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    candidates = sorted(
        [
            path
            for path in data_dir.iterdir()
            if path.is_file() and path.suffix.lower() in TABULAR_EXTENSIONS and not path.name.startswith("~$")
        ]
    )
    if not candidates:
        raise FileNotFoundError(f"No .csv/.xls/.xlsx dataset found in: {data_dir}")
    return candidates


def _build_rename_map(columns: Iterable[str]) -> Dict[str, str]:
    normalized_to_source: Dict[str, str] = {}
    lower_map = {str(col).strip().lower(): str(col) for col in columns}

    for normalized_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            source = lower_map.get(alias.lower())
            if source:
                normalized_to_source[source] = normalized_name
                break
    return normalized_to_source


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk"]
        last_error: Exception | None = None
        for enc in encodings:
            try:
                return pd.read_csv(path, encoding=enc)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(f"无法解码 CSV 文件: {path}") from last_error

    try:
        return pd.read_excel(path)
    except ImportError as exc:
        raise ImportError("读取 .xlsx 需要 openpyxl，请先安装 requirements.txt 中依赖") from exc


def _clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _parse_salary(salary_desc: str) -> Tuple[int, int, int]:
    text = (salary_desc or "").strip().lower()
    if not text:
        return 0, 0, 0

    months = 12
    m = re.search(r"(\d{1,2})\s*薪", text)
    if m:
        months = int(m.group(1))

    # 去掉月薪标识，便于区间解析；时薪/日薪按月折算（21个工作日、8小时/天）
    text = text.replace("/月", "").replace("每月", "")

    multiplier = 1
    if "元/时" in text or "元/小时" in text:
        multiplier = int(8 * 21)
    elif "元/天" in text or "元/日" in text:
        multiplier = int(21)

    normalized = (
        text.replace("元/时", "")
        .replace("元/小时", "")
        .replace("元/天", "")
        .replace("元/日", "")
        .replace("元", "")
    )

    range_pattern = re.search(
        r"(\d+(?:\.\d+)?)\s*([kw万千]?)\s*[-~至]\s*(\d+(?:\.\d+)?)\s*([kw万千]?)",
        normalized,
    )
    if range_pattern:
        left = float(range_pattern.group(1))
        left_unit = range_pattern.group(2)
        right = float(range_pattern.group(3))
        right_unit = range_pattern.group(4)
        if not left_unit and right_unit:
            left_unit = right_unit
        if not right_unit and left_unit:
            right_unit = left_unit
        return (
            _salary_to_int(left, left_unit) * multiplier,
            _salary_to_int(right, right_unit) * multiplier,
            months,
        )

    single_pattern = re.search(r"(\d+(?:\.\d+)?)\s*([kw万千]?)", normalized)
    if single_pattern:
        amount = _salary_to_int(float(single_pattern.group(1)), single_pattern.group(2)) * multiplier
        return amount, amount, months

    return 0, 0, months


def _salary_to_int(amount: float, unit: str) -> int:
    unit = (unit or "").lower()
    if unit == "k" or unit == "千":
        return int(amount * 1000)
    if unit == "w" or unit == "万":
        return int(amount * 10000)
    return int(amount)


def _split_labels(raw: str) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"[,，;；|、]+", raw)
    return [p.strip() for p in parts if p.strip()]


def _extract_job_id(job_id: str, job_href: str) -> str:
    direct = _clean_text(job_id)
    if direct:
        return direct
    href = _clean_text(job_href)
    m = re.search(r"/jobs/(\d+)\.html", href)
    if m:
        return m.group(1)
    return ""


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = _build_rename_map(df.columns)
    normalized = df.rename(columns=rename_map).copy()

    expected = list(COLUMN_ALIASES.keys())
    for col in expected:
        if col not in normalized.columns:
            normalized[col] = ""

    normalized = normalized[expected]
    for col in expected:
        normalized[col] = normalized[col].apply(_clean_text)

    normalized = normalized[normalized["job_name"] != ""].reset_index(drop=True)
    return normalized


def _rows_to_jobs(df: pd.DataFrame) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        salary_min, salary_max, salary_months = _parse_salary(row.get("salary_desc", ""))
        city_name = row.get("city_name", "")
        job_id = _extract_job_id(row.get("job_id", ""), row.get("job_href", ""))
        labels = _split_labels(row.get("job_labels", ""))
        skills = _split_labels(row.get("skills", ""))

        jobs.append(
            {
                "job_id": job_id,
                "job_name": row.get("job_name", ""),
                "salary_desc": row.get("salary_desc", ""),
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_months": salary_months,
                "city_name": city_name,
                "area_district": city_name,
                "business_district": "",
                "experience": row.get("experience", ""),
                "education": row.get("education", ""),
                "job_type": row.get("job_type", ""),
                "skills": skills,
                "job_labels": labels,
                "company_name": row.get("company_name", ""),
                "company_scale": row.get("company_scale", ""),
                "industry": row.get("industry", ""),
                "job_description": row.get("job_description", ""),
                "url": row.get("job_href", ""),
                "address": row.get("address", "") or city_name,
                "scraped_at": row.get("scraped_at", ""),
            }
        )
    return jobs


def _dedup_jobs_in_batch(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    key_to_index: Dict[str, int] = {}
    result: List[Dict[str, Any]] = []
    for job in jobs:
        job_id = str(job.get("job_id", "")).strip()
        if job_id:
            key = f"job_id:{job_id}"
        else:
            key = "fallback:" + "|".join(
                [
                    str(job.get("job_name", "")).strip(),
                    str(job.get("company_name", "")).strip(),
                    str(job.get("city_name", "")).strip(),
                    str(job.get("salary_desc", "")).strip(),
                ]
            )
        if key not in key_to_index:
            key_to_index[key] = len(result)
            result.append(job)
            continue

        old_idx = key_to_index[key]
        old_job = result[old_idx]
        old_url = str(old_job.get("url", "") or "").strip()
        new_url = str(job.get("url", "") or "").strip()

        # 同一岗位冲突时，优先保留带 URL 的记录，避免丢失职位链接。
        if not old_url and new_url:
            result[old_idx] = job
    return result


def import_tabular_jobs_to_career_db(data_dir: Path) -> Dict[str, int]:
    datasets = locate_tabular_datasets(data_dir)

    all_jobs: List[Dict[str, Any]] = []
    rows_before_clean = 0
    rows_after_clean = 0
    skipped_files = 0

    for dataset in datasets:
        try:
            df = _read_table(dataset)
        except Exception as exc:
            skipped_files += 1
            print(f"跳过文件 {dataset.name}: {exc}")
            continue
        rows_before_clean += int(len(df))
        clean_df = _normalize_dataframe(df)
        rows_after_clean += int(len(clean_df))
        all_jobs.extend(_rows_to_jobs(clean_df))

    if not all_jobs:
        return {
            "files": len(datasets),
            "skipped_files": skipped_files,
            "rows_before_clean": 0,
            "rows_after_clean": 0,
            "batch_unique": 0,
            "inserted": 0,
            "duplicated": 0,
            "total_processed": 0,
        }

    unique_jobs = _dedup_jobs_in_batch(all_jobs)
    upsert_result = upsert_jobs_to_vector_store(unique_jobs, data_dir)

    return {
        "files": len(datasets),
        "skipped_files": skipped_files,
        "rows_before_clean": rows_before_clean,
        "rows_after_clean": rows_after_clean,
        "batch_unique": len(unique_jobs),
        "inserted": upsert_result["inserted"],
        "duplicated": upsert_result["duplicated"],
        "total_processed": upsert_result["total"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="将 data 目录中的 CSV/Excel 清洗并增量写入向量数据库")
    parser.add_argument("--data-dir", default="data", help="数据目录，默认 data")
    args = parser.parse_args()

    result = import_tabular_jobs_to_career_db(Path(args.data_dir))
    print("导入完成:")
    print(f"  文件数: {result['files']}")
    print(f"  跳过文件: {result['skipped_files']}")
    print(f"  清洗前行数: {result['rows_before_clean']}")
    print(f"  清洗后行数: {result['rows_after_clean']}")
    print(f"  批内去重后: {result['batch_unique']}")
    print(f"  新增写入: {result['inserted']}")
    print(f"  已存在跳过: {result['duplicated']}")


if __name__ == "__main__":
    main()

