from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable

import requests


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str


class LLMClient:
    def __init__(self, api_key: str = "", base_url: str = "", model: str = "") -> None:
        self.config = LLMConfig(
            api_key=str(api_key or "").strip(),
            base_url=str(base_url or "https://api.openai.com/v1").strip(),
            model=str(model or "gpt-4o-mini").strip(),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.config.api_key)

    def _url(self) -> str:
        base = self.config.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/chat/completions"

    def generate_text(self, system_prompt: str, user_prompt: str, max_tokens: int = 1400) -> str:
        if not self.enabled:
            return ""

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(self._url(), json=payload, headers=headers, timeout=(10, 60))
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return str(content).strip()
        except Exception:
            return ""

    def stream_text(self, system_prompt: str, user_prompt: str, max_tokens: int = 2200) -> Iterable[str]:
        if not self.enabled:
            return

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            with requests.post(
                self._url(),
                json=payload,
                headers=headers,
                timeout=(10, 180),
                stream=True,
            ) as resp:
                resp.raise_for_status()
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = str(raw_line).strip()
                    if not line.startswith("data:"):
                        continue
                    data_part = line[5:].strip()
                    if data_part == "[DONE]":
                        break
                    try:
                        data = json.loads(data_part)
                    except Exception:
                        continue

                    delta = (
                        data.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content", "")
                    )
                    if delta:
                        yield str(delta)
            return
        except Exception:
            # Fall back to non-streaming text and chunk it for UI streaming.
            text = self.generate_text(system_prompt, user_prompt, max_tokens=max_tokens)
            if not text:
                return
            step = 48
            for i in range(0, len(text), step):
                yield text[i : i + step]

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        raw = self.generate_text(system_prompt, user_prompt, max_tokens=1000)
        if not raw:
            return {}

        try:
            return json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except Exception:
                    return {}
            return {}
