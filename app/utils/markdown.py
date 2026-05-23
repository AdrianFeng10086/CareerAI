"""Markdown 渲染辅助。"""

from __future__ import annotations

import importlib


def render_markdown_to_html(content: str) -> str:
    """将 Markdown 渲染为 HTML，若依赖缺失则返回空字符串。"""
    try:
        md_module = importlib.import_module("markdown")
    except Exception:
        return ""

    return md_module.markdown(
        content,
        extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
    )
