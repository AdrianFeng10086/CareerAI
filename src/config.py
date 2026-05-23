"""配置管理模块。

所有配置都从项目根目录下的 `.env` 文件读取(也支持进程环境变量覆盖)。
运行时变更(例如 Boss Cookie / BST 更新)通过 `Config.save()` 写回 `.env`,
保留原文件中已有键的顺序与注释。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from .env_file import get_env_path, load_env, update_env


_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    """首次访问配置前把 .env 加载到 os.environ。"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    load_env(override=False)
    _ENV_LOADED = True


# (env_key, attr_name, type) — 主映射,save 时按此顺序写回 .env
_FIELD_SPEC: Tuple[Tuple[str, str, type], ...] = (
    ("MCP_SERVER_URL", "mcp_server_url", str),
    ("AI_API_KEY", "ai_api_key", str),
    ("AI_BASE_URL", "ai_base_url", str),
    ("AI_MODEL", "ai_model", str),
    ("AI_TEMPERATURE", "ai_temperature", float),
    ("AI_MAX_TOKENS", "ai_max_tokens", int),
    ("BACKUP_AI_API_KEY", "backup_ai_api_key", str),
    ("BACKUP_AI_BASE_URL", "backup_ai_base_url", str),
    ("BACKUP_AI_MODEL", "backup_ai_model", str),
    ("BACKUP_AI_ENABLE_ENHANCEMENT", "backup_ai_enable_enhancement", bool),
    ("REQUEST_DELAY", "request_delay", float),
    ("MAX_RETRY", "max_retry", int),
    ("MAX_PAGES_PER_SEARCH", "max_pages_per_search", int),
    ("DATA_DIR", "data_dir", str),
    ("OUTPUT_DIR", "output_dir", str),
    ("LAST_SEARCH_TIME", "last_search_time", str),
    ("BOSS_COOKIE", "cookie", str),
    ("BOSS_BST", "bst", str),
)

# 同一属性可接受多个别名 env (优先级:主键 > 别名)
_FIELD_ALIASES: Dict[str, Tuple[str, ...]] = {
    "ai_api_key": ("OPENAI_API_KEY",),
    "ai_base_url": ("OPENAI_BASE_URL",),
    "backup_ai_api_key": ("HUNYUAN_API_KEY",),
    "backup_ai_base_url": ("HUNYUAN_BASE_URL",),
    "backup_ai_model": ("HUNYUAN_MODEL",),
}


def _coerce(value: str, target_type: type):
    if target_type is bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if target_type is int:
        try:
            return int(float(str(value).strip()))
        except Exception:
            return 0
    if target_type is float:
        try:
            return float(str(value).strip())
        except Exception:
            return 0.0
    return str(value)


@dataclass
class Config:
    """全局配置(由 .env 驱动)。"""

    mcp_server_url: str = "http://127.0.0.1:8000"

    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_temperature: float = 0.7
    ai_max_tokens: int = 4096

    backup_ai_api_key: str = ""
    backup_ai_base_url: str = "https://api.hunyuan.cloud.tencent.com/v1/chat/completions"
    backup_ai_model: str = "hunyuan-turbos-latest"
    backup_ai_enable_enhancement: bool = True

    request_delay: float = 1.5
    max_retry: int = 3
    max_pages_per_search: int = 5

    data_dir: str = "data"
    output_dir: str = "output"
    last_search_time: str = ""

    cookie: str = ""
    bst: str = ""

    @classmethod
    def load(cls, _config_path: str | None = None) -> "Config":
        """从 `.env` + 进程环境变量加载配置。

        `_config_path` 仅为保持旧调用签名兼容,不再使用。
        """
        _ensure_env_loaded()
        config = cls()

        for env_key, attr_name, attr_type in _FIELD_SPEC:
            raw = os.environ.get(env_key)
            if raw is None:
                for alias in _FIELD_ALIASES.get(attr_name, ()):  # type: ignore[arg-type]
                    if os.environ.get(alias) is not None:
                        raw = os.environ.get(alias)
                        break
            if raw is not None and raw != "":
                setattr(config, attr_name, _coerce(raw, attr_type))

        base_dir = Path(__file__).resolve().parent.parent
        (base_dir / config.data_dir).mkdir(parents=True, exist_ok=True)
        (base_dir / config.output_dir).mkdir(parents=True, exist_ok=True)

        return config

    def save(self, _config_path: str | None = None) -> None:
        """把当前配置写回 `.env`(原地更新,保留注释/顺序)。"""
        updates: Dict[str, str] = {}
        for env_key, attr_name, attr_type in _FIELD_SPEC:
            value = getattr(self, attr_name)
            if attr_type is bool:
                updates[env_key] = "true" if value else "false"
            else:
                updates[env_key] = "" if value is None else str(value)

        update_env(updates)
        print(f"配置已保存到: {get_env_path()}")
