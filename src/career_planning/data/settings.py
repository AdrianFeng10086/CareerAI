from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


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


def load_settings(base_dir: Path) -> Settings:
    config_path = base_dir / "config.json"
    data = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    settings = Settings(
        app_host=str(data.get("app_host", "127.0.0.1")),
        app_port=int(data.get("app_port", 5050)),
        app_debug=bool(data.get("app_debug", True)),
        data_dir=str(data.get("data_dir", "data")),
        output_dir=str(data.get("output_dir", "output")),
        llm_api_key=str(data.get("openai_api_key", "")),
        llm_base_url=str(data.get("openai_base_url", "https://api.openai.com/v1")),
        llm_model=str(data.get("openai_model", "gpt-4o-mini")),
        export_default_format=str(data.get("export_default_format", "pdf")).lower(),
    )

    # Environment variables override config file values.
    if os.getenv("APP_HOST"):
        settings.app_host = str(os.getenv("APP_HOST", settings.app_host))
    if os.getenv("APP_PORT"):
        settings.app_port = int(os.getenv("APP_PORT", str(settings.app_port)))
    if os.getenv("APP_DEBUG"):
        settings.app_debug = _to_bool(os.getenv("APP_DEBUG", ""))

    if os.getenv("DATA_DIR"):
        settings.data_dir = str(os.getenv("DATA_DIR", settings.data_dir))
    if os.getenv("OUTPUT_DIR"):
        settings.output_dir = str(os.getenv("OUTPUT_DIR", settings.output_dir))

    if os.getenv("OPENAI_API_KEY"):
        settings.llm_api_key = str(os.getenv("OPENAI_API_KEY", settings.llm_api_key))
    if os.getenv("OPENAI_BASE_URL"):
        settings.llm_base_url = str(os.getenv("OPENAI_BASE_URL", settings.llm_base_url))
    if os.getenv("OPENAI_MODEL"):
        settings.llm_model = str(os.getenv("OPENAI_MODEL", settings.llm_model))

    if os.getenv("EXPORT_DEFAULT_FORMAT"):
        settings.export_default_format = str(
            os.getenv("EXPORT_DEFAULT_FORMAT", settings.export_default_format)
        ).lower()

    if settings.export_default_format not in {"pdf", "html", "markdown"}:
        settings.export_default_format = "pdf"

    return settings