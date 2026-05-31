"""Cloud chat client for optional cloud generation.

Used only when a request explicitly opts into the cloud provider and the egress
gate (air-gap switch + anonymization in :mod:`app.privacy.egress`) allows it.
Kept httpx-only so the sidecar stays light. Speaks two protocols:

* OpenAI-compatible ``/chat/completions`` (OpenAI, OpenRouter, Together, Groq,
  remote vLLM, ...).
* Native Anthropic Messages API (``/v1/messages``), auto-detected from the
  endpoint host or an ``sk-ant-`` API key.
"""
from __future__ import annotations

import httpx

from app.config import get_settings

_ANTHROPIC_VERSION = "2023-06-01"


def _is_anthropic(base_url: str, api_key: str) -> bool:
    return "anthropic.com" in base_url or api_key.startswith("sk-ant-")


class CloudClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.cloud_base_url).rstrip("/")
        self.api_key = api_key or settings.cloud_api_key
        self.model = model or settings.cloud_model

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Single-turn generation against the configured cloud endpoint."""
        if not self.api_key:
            raise RuntimeError(
                "Provider cloud non configurato: imposta KB_CLOUD_API_KEY "
                "(ed eventualmente KB_CLOUD_BASE_URL / KB_CLOUD_MODEL)."
            )
        model = model or self.model
        if _is_anthropic(self.base_url, self.api_key):
            return await self._generate_anthropic(prompt, system, model, temperature)
        return await self._generate_openai(prompt, system, model, temperature)

    async def _generate_openai(
        self, prompt: str, system: str | None, model: str, temperature: float
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages, "temperature": temperature},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"] or ""

    async def _generate_anthropic(
        self, prompt: str, system: str | None, model: str, temperature: float
    ) -> str:
        base = self.base_url
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        if "anthropic.com" not in base:
            base = "https://api.anthropic.com"
        payload: dict = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{base}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": _ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            parts = data.get("content", [])
            return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
