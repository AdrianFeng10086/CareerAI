"""通用小工具:类型转换。"""

from __future__ import annotations

from typing import Any


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
