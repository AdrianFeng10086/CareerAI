"""LLM 客户端构建工具。"""

from __future__ import annotations

from src.career_planning.ai.llm_client import LLMClient as CareerLLMClient
from src.config import Config


def build_chat_completions_url(base_url: str) -> str:
    """将配置中的 base_url 规范化为 chat/completions 完整地址。"""
    url = str(base_url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/chat/completions"


def build_career_llm_client() -> CareerLLMClient:
    cfg = Config.load()

    api_key = str(cfg.ai_api_key or "").strip()
    base_url = str(cfg.ai_base_url or "").strip()
    model = str(cfg.ai_model or "").strip()

    if not api_key and cfg.backup_ai_api_key:
        api_key = str(cfg.backup_ai_api_key or "").strip()
        base_url = str(cfg.backup_ai_base_url or "").strip()
        model = str(cfg.backup_ai_model or "").strip()

    return CareerLLMClient(api_key=api_key, base_url=base_url, model=model)
