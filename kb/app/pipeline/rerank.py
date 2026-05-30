"""Reranking layer.

After hybrid retrieval we have a candidate pool that is good on recall but noisy
on precision. Reranking re-scores the candidates against the query so the few
chunks that actually answer it float to the top — crucial for weak models with a
small context window.

Default strategy is an LLM pointwise reranker that runs on the models we already
have in Ollama (no extra service). It asks the model to score each candidate's
relevance 0-10 in JSON. A cross-encoder (bge-reranker-v2-m3) can be plugged in
later behind the same interface.
"""
from __future__ import annotations

import json

from app.ollama_client import OllamaClient
from app.schema import RetrievedChunk

_SYSTEM = (
    "Sei un giudice di pertinenza. Dato una domanda e un passaggio, valuti quanto "
    "il passaggio aiuta a rispondere alla domanda. Rispondi SOLO con JSON "
    '{"score": <intero 0-10>} dove 0=irrilevante, 10=risposta diretta.'
)


class Reranker:
    def __init__(self, ollama: OllamaClient | None = None) -> None:
        self.ollama = ollama or OllamaClient()

    async def _score(self, query: str, text: str, model: str | None) -> float:
        prompt = (
            f"Domanda:\n{query}\n\nPassaggio:\n\"\"\"\n{text[:2000]}\n\"\"\"\n\n"
            "Valuta la pertinenza."
        )
        raw = await self.ollama.generate(
            prompt, system=_SYSTEM, temperature=0.0, json_mode=True, model=model
        )
        try:
            score = float(json.loads(raw).get("score", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            score = 0.0
        return max(0.0, min(10.0, score)) / 10.0

    async def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int, model: str | None = None
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []
        for item in candidates:
            item.rerank_score = await self._score(query, item.chunk.text, model)
        ranked = sorted(candidates, key=lambda c: (c.rerank_score or 0.0), reverse=True)
        return ranked[:top_k]
