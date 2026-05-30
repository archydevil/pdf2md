"""LanceDB-backed store: dense vectors + full-text (BM25) for hybrid retrieval.

LanceDB is embedded (no server, just files under data_dir) which is ideal for an
air-gapped setup. We keep a flat row per chunk with the embedding plus the most
useful filterable metadata promoted to columns.
"""
from __future__ import annotations

import json
from typing import Any

import lancedb
import pyarrow as pa

from app.config import get_settings
from app.schema import Chunk, Classification, Provenance, RetrievedChunk

_TABLE = "chunks"


def _schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("doc_id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("context_prefix", pa.string()),
            pa.field("embed_text", pa.string()),  # indexed for BM25
            pa.field("vector", pa.list_(pa.float32(), dim)),
            # Promoted, filterable metadata
            pa.field("source_kind", pa.string()),
            pa.field("file_name", pa.string()),
            pa.field("page", pa.int32()),
            pa.field("lang", pa.string()),
            pa.field("doc_type", pa.string()),
            pa.field("sensitivity", pa.string()),
            pa.field("pii_redacted", pa.bool_()),
            # Full JSON blobs for loss-less round-trips
            pa.field("provenance_json", pa.string()),
            pa.field("classification_json", pa.string()),
            pa.field("parent_id", pa.string()),
            pa.field("content_hash", pa.string()),
            pa.field("version", pa.int32()),
        ]
    )


class KBStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.db = lancedb.connect(str(settings.lancedb_dir))
        self.dim = settings.embed_dim
        if _TABLE in self.db.table_names():
            self.table = self.db.open_table(_TABLE)
        else:
            self.table = self.db.create_table(_TABLE, schema=_schema(self.dim))
            self._ensure_fts()

    def _ensure_fts(self) -> None:
        try:
            self.table.create_fts_index("embed_text", replace=True)
        except Exception:
            # FTS index is best-effort; vector search still works without it.
            pass

    def _row(self, chunk: Chunk, vector: list[float]) -> dict[str, Any]:
        p = chunk.provenance
        c = chunk.classification
        return {
            "id": chunk.id,
            "doc_id": chunk.doc_id,
            "text": chunk.text,
            "context_prefix": chunk.context_prefix,
            "embed_text": chunk.embedding_text(),
            "vector": vector,
            "source_kind": p.source_kind.value,
            "file_name": p.file_name,
            "page": p.page or -1,
            "lang": c.lang,
            "doc_type": c.doc_type or "",
            "sensitivity": c.sensitivity.value,
            "pii_redacted": chunk.pii_redacted,
            "provenance_json": p.model_dump_json(),
            "classification_json": c.model_dump_json(),
            "parent_id": chunk.parent_id or "",
            "content_hash": chunk.content_hash,
            "version": chunk.version,
        }

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        if not chunks:
            return 0
        ids = [c.id for c in chunks]
        # Idempotent upsert: delete existing ids, then add.
        id_list = ",".join(f"'{i}'" for i in ids)
        try:
            self.table.delete(f"id IN ({id_list})")
        except Exception:
            pass
        rows = [self._row(c, v) for c, v in zip(chunks, vectors)]
        self.table.add(rows)
        self._ensure_fts()
        return len(rows)

    def _to_retrieved(self, rec: dict[str, Any], score: float) -> RetrievedChunk:
        provenance = Provenance(**json.loads(rec["provenance_json"]))
        classification = Classification(**json.loads(rec["classification_json"]))
        chunk = Chunk(
            id=rec["id"],
            doc_id=rec["doc_id"],
            text=rec["text"],
            context_prefix=rec.get("context_prefix", ""),
            provenance=provenance,
            classification=classification,
            parent_id=rec.get("parent_id") or None,
            content_hash=rec.get("content_hash", ""),
            pii_redacted=bool(rec.get("pii_redacted", False)),
            version=int(rec.get("version", 1)),
        )
        return RetrievedChunk(chunk=chunk, score=score)

    def search_vector(self, vector: list[float], k: int, where: str | None = None) -> list[RetrievedChunk]:
        q = self.table.search(vector).metric("cosine").limit(k)  # type: ignore[attr-defined]
        if where:
            q = q.where(where, prefilter=True)
        results = q.to_list()
        out = []
        for r in results:
            dist = float(r.get("_distance", 1.0))
            out.append(self._to_retrieved(r, score=1.0 - dist))
        return out

    def search_text(self, query: str, k: int, where: str | None = None) -> list[RetrievedChunk]:
        try:
            q = self.table.search(query, query_type="fts").limit(k)
            if where:
                q = q.where(where, prefilter=True)
            results = q.to_list()
        except Exception:
            return []
        return [self._to_retrieved(r, score=float(r.get("_score", 0.0))) for r in results]

    def count(self) -> int:
        try:
            return self.table.count_rows()
        except Exception:
            return 0

    def all_chunks(self) -> list[Chunk]:
        """Return every stored chunk (for graph building / exports)."""
        try:
            records = self.table.to_pandas().to_dict("records")
        except Exception:
            return []
        return [self._to_retrieved({str(k): v for k, v in r.items()}, score=0.0).chunk for r in records]
