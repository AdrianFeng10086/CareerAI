"""读写项目根目录 .env 文件的轻量工具。

- `get_env_path()`  返回项目根目录下的 .env 路径
- `load_env()`      调用 python-dotenv 把 .env 加载到 os.environ (默认覆盖)
- `update_env()`    原地更新 .env 文件中若干键值,保留原有顺序与注释,新增键追加到末尾

写入时会按需对值加双引号 + 转义,以兼容 dotenv 解析规则。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Mapping


_ROOT_DIR = Path(__file__).resolve().parent.parent


def get_env_path() -> Path:
    """返回项目根目录下的 .env 路径。"""
    return _ROOT_DIR / ".env"


def load_env(override: bool = True) -> None:
    """把 .env 中的键值加载到 os.environ。

    若 python-dotenv 未安装,则使用兜底解析。
    """
    env_path = get_env_path()
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=str(env_path), override=override)
        return
    except Exception:
        pass

    for key, value in _parse_env_file(env_path).items():
        if override or key not in os.environ:
            os.environ[key] = value


def update_env(updates: Mapping[str, str]) -> None:
    """原地更新 .env 文件,保留已有键的位置与注释,缺失键追加到末尾。"""
    env_path = get_env_path()
    existing_lines: List[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    new_lines: List[str] = []
    for raw in existing_lines:
        stripped = raw.strip()
        if (not stripped) or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(raw)
            continue

        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={_quote(updates[key])}")
            seen.add(key)
        else:
            new_lines.append(raw)

    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={_quote(value)}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    # 同步更新到当前进程的 os.environ
    for key, value in updates.items():
        os.environ[key] = str(value)


def _quote(value) -> str:
    """根据值中的特殊字符决定是否加双引号并转义。"""
    s = "" if value is None else str(value)
    if s == "":
        return ""
    needs_quote = any(c in s for c in (" ", "\t", "\"", "\n", "\r", "#", "$", "`", "'"))
    if not needs_quote:
        return s
    escaped = s.replace("\\", "\\\\").replace("\"", "\\\"")
    return f'"{escaped}"'


def _parse_env_file(path: Path) -> Dict[str, str]:
    """兜底解析:逐行读取 KEY=VALUE,支持双引号包裹与简单转义。"""
    result: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] == '"':
            val = val[1:-1].replace("\\\"", "\"").replace("\\\\", "\\")
        result[key] = val
    return result
