from __future__ import annotations

import io
from pathlib import Path


def _parse_pdf_bytes(raw: bytes) -> str:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(io.BytesIO(raw))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def _parse_docx_bytes(raw: bytes) -> str:
    from docx import Document  # type: ignore

    doc = Document(io.BytesIO(raw))
    lines = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(lines).strip()


def parse_resume_file(filename: str, raw: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf_bytes(raw)
    if suffix == ".docx":
        return _parse_docx_bytes(raw)
    if suffix == ".doc":
        raise ValueError("暂不支持 .doc，请另存为 .docx 或 PDF 后上传。")
    raise ValueError("仅支持 PDF、DOCX、DOC 文件。")
