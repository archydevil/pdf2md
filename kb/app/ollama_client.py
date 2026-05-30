"""Thin async client for Ollama — the only model runtime we touch.

Kept dependency-free (httpx only) so the sidecar stays light and fully local.
"""
from __future__ import annotations

import httpx

from app.config import get_settings


class OllamaClient:
    def __init__(self, host: str | None = None) -> None:
        self.host = (host or get_settings().ollama_host).rstrip("/")

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Return one dense embedding per input text using bge-m3 by default."""
        settings = get_settings()
        model = model or settings.embed_model
        out: list[list[float]] = []
        async with httpx.AsyncClient(timeout=120) as client:
            # Ollama's /api/embed accepts batched input on recent versions.
            resp = await client.post(
                f"{self.host}/api/embed",
                json={"model": model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            out = data.get("embeddings") or []
        if len(out) != len(texts):
            raise RuntimeError(f"Embedding count mismatch: {len(out)} != {len(texts)}")
        return out

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> str:
        """Single-turn generation. temperature=0 for deterministic enrichment."""
        settings = get_settings()
        model = model or settings.llm_model
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(f"{self.host}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.host}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False
