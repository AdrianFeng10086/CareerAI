from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.env_file import load_env


_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    load_env(override=False)
    _ENV_LOADED = True


@dataclass
class Settings:
    app_host: str = "127.0.0.1"
    app_port: int = 5050
    app_debug: bool = True

    data_dir: str = "data"
    output_dir: str = "output"

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    export_default_format: str = "pdf"


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_settings(_base_dir: Path | None = None) -> Settings:
    """从 .env 与进程环境变量加载 Settings。

    `_base_dir` 仅为兼容旧调用签名,不再使用。
    """
    _ensure_env_loaded()
    settings = Settings()

    if os.getenv("APP_HOST"):
        settings.app_host = str(os.getenv("APP_HOST", settings.app_host))
    if os.getenv("APP_PORT"):
        try:
            settings.app_port = int(os.getenv("APP_PORT", str(settings.app_port)))
        except Exception:
            pass
    if os.getenv("APP_DEBUG"):
        settings.app_debug = _to_bool(os.getenv("APP_DEBUG", ""))

    if os.getenv("DATA_DIR"):
        settings.data_dir = str(os.getenv("DATA_DIR", settings.data_dir))
    if os.getenv("OUTPUT_DIR"):
        settings.output_dir = str(os.getenv("OUTPUT_DIR", settings.output_dir))

    # 与主 Config 共用 AI 密钥/Base/Model;同时兼容历史的 OPENAI_* 变量
    api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if api_key:
        settings.llm_api_key = api_key
    base_url = os.getenv("AI_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if base_url:
        settings.llm_base_url = base_url
    model = os.getenv("AI_MODEL") or os.getenv("OPENAI_MODEL")
    if model:
        settings.llm_model = model

    if os.getenv("EXPORT_DEFAULT_FORMAT"):
        settings.export_default_format = str(
            os.getenv("EXPORT_DEFAULT_FORMAT", settings.export_default_format)
        ).lower()

    if settings.export_default_format not in {"pdf", "html", "markdown"}:
        settings.export_default_format = "pdf"

    return settings
