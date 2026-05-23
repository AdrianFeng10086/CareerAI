"""报告文件管理服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.services.auth_service import get_user_output_dir


def collect_report_files(user: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    output_dir = get_user_output_dir(user)
    output_dir.mkdir(parents=True, exist_ok=True)

    items: List[Dict[str, Any]] = []
    for file_path in output_dir.glob("*"):
        if not file_path.is_file():
            continue
        # 前端列表仅保留 .html，过滤 .md 和 .pdf
        if file_path.suffix.lower() != ".html":
            continue
        stat = file_path.stat()
        items.append(
            {
                "name": file_path.name,
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "suffix": file_path.suffix.lower(),
            }
        )

    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def resolve_report_pdf_file(output_dir: Path, report_name: str) -> Path | None:
    """按报告名解析可用 PDF，兼容 HTML/PDF 生成时间戳存在秒级偏差的场景。"""
    raw_name = str(report_name or "").strip()
    if not raw_name:
        return None

    requested = (output_dir / raw_name).resolve()
    if output_dir in requested.parents and requested.exists() and requested.suffix.lower() == ".pdf":
        return requested

    requested_path = Path(raw_name)
    requested_suffix = requested_path.suffix.lower()
    if requested_suffix not in {".html", ".pdf"}:
        return None

    html_name = raw_name if requested_suffix == ".html" else f"{requested_path.stem}.html"
    html_path = (output_dir / html_name).resolve()
    if output_dir not in html_path.parents or not html_path.exists():
        return None

    direct_pdf = (output_dir / f"{html_path.stem}.pdf").resolve()
    if output_dir in direct_pdf.parents and direct_pdf.exists():
        return direct_pdf

    family_prefix = ""
    if html_path.name.startswith("report_"):
        family_prefix = "report_"
    elif html_path.name.startswith("career_plan_"):
        family_prefix = "career_plan_"

    candidates = [
        p for p in output_dir.glob("*.pdf") if not family_prefix or p.name.startswith(family_prefix)
    ]
    if not candidates:
        return None

    html_mtime = html_path.stat().st_mtime
    nearest = min(candidates, key=lambda p: abs(p.stat().st_mtime - html_mtime))
    if abs(nearest.stat().st_mtime - html_mtime) <= 300:
        return nearest
    return None
