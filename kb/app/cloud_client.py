"""OpenAI-compatible chat client for optional cloud generation.

Used only when a request explicitly opts into the cloud provider and the egress
gate (air-gap switch + anonymization in :mod:`app.privacy.egress`) allows it.
Kept httpx-only so the sidecar stays light. Works with any endpoint that speaks
``/chat/completions`` (OpenAI, OpenRouter, Together, Groq, remote vLLM, ...).
"""
from __future__ import annotations

import httpx

from app.config import get_settings


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
        """Single-turn generation against an OpenAI-compatible endpoint."""
        if not self.api_key:
            raise RuntimeError(
                "Provider cloud non configurato: imposta KB_CLOUD_API_KEY "
                "(ed eventualmente KB_CLOUD_BASE_URL / KB_CLOUD_MODEL)."
            )
        model = model or self.model
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
