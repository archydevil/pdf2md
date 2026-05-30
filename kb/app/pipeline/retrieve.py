"""Hybrid retrieval: dense (bge-m3) + sparse (BM25) fused with Reciprocal Rank
Fusion, with optional cross-encoder reranking. This is the layer that makes weak
models answer well, by maximizing the relevance of the small context window.
"""
from __future__ import annotations

from app.ollama_client import OllamaClient
from app.schema import RetrievedChunk
from app.store.lancedb_store import KBStore


def reciprocal_rank_fusion(
    rankings: list[list[RetrievedChunk]], k: int = 60
) -> list[RetrievedChunk]:
    """Combine multiple ranked lists. RRF is robust and score-scale agnostic."""
    scores: dict[str, float] = {}
    best: dict[str, RetrievedChunk] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            cid = item.chunk.id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            if cid not in best:
                best[cid] = item
    fused = []
    for cid, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
        item = best[cid]
        item.score = score
        fused.append(item)
    return fused


class Retriever:
    def __init__(self, store: KBStore | None = None, ollama: OllamaClient | None = None) -> None:
        self.store = store or KBStore()
        self.ollama = ollama or OllamaClient()

    async def search(
        self, query: str, k: int = 8, where: str | None = None
    ) -> list[RetrievedChunk]:
        # Dense
        vec = (await self.ollama.embed([query]))[0]
        dense = self.store.search_vector(vec, k=k * 3, where=where)
        # Sparse
        sparse = self.store.search_text(query, k=k * 3, where=where)
        # Fuse
        fused = reciprocal_rank_fusion([dense, sparse])
        return fused[:k]
