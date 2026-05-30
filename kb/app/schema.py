"""Pydantic schema for the Knowledge Base.

The chunk is the atomic, retrievable unit. It is intentionally rich: stable IDs,
provenance, contextual prefix (Anthropic-style Contextual Retrieval) and a
detailed classification block. This is what lets even small local models answer
accurately with verifiable citations.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def stable_hash(*parts: str) -> str:
    """Deterministic short hash used for IDs and dedup."""
    h = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return h[:16]


class Sensitivity(str, Enum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


class SourceKind(str, Enum):
    pdf = "pdf"
    docx = "docx"
    text = "text"
    markdown = "markdown"
    image = "image"  # scanned -> OCR
    email = "email"
    html = "html"
    transcript = "transcript"  # Meetily STT
    other = "other"


class Provenance(BaseModel):
    """Where a chunk physically comes from — enables citations."""

    file_name: str
    source_kind: SourceKind = SourceKind.other
    page: int | None = None
    section_path: list[str] = Field(default_factory=list)  # e.g. ["3 Recesso", "3.1"]
    char_start: int | None = None
    char_end: int | None = None
    # For transcripts: speaker + media timestamps (seconds).
    speaker: str | None = None
    t_start: float | None = None
    t_end: float | None = None


class Classification(BaseModel):
    """Detailed, filterable metadata. Filled by the local LLM + heuristics."""

    lang: str = "und"
    doc_type: str | None = None  # contratto, fattura, verbale, paper, ...
    taxonomy: list[str] = Field(default_factory=list)  # controlled-vocab paths
    topics: list[str] = Field(default_factory=list)
    entities: dict[str, list[str]] = Field(default_factory=dict)  # {person, org, date, money, ...}
    sensitivity: Sensitivity = Sensitivity.internal
    keywords: list[str] = Field(default_factory=list)
    summary: str | None = None


class Chunk(BaseModel):
    id: str
    doc_id: str
    text: str
    # Anthropic Contextual Retrieval: short LLM-generated context prepended at
    # embed/index time so the chunk is self-explanatory for weak models.
    context_prefix: str = ""
    provenance: Provenance
    classification: Classification = Field(default_factory=Classification)
    # Parent-child retrieval: small chunk matches, parent gives full context.
    parent_id: str | None = None
    token_count: int | None = None
    content_hash: str = ""
    pii_redacted: bool = False
    version: int = 1
    created_at: datetime = Field(default_factory=_utcnow)

    def embedding_text(self) -> str:
        """Text actually fed to the embedder: context + content."""
        return f"{self.context_prefix}\n\n{self.text}".strip() if self.context_prefix else self.text

    @classmethod
    def make_id(cls, doc_id: str, section: str, index: int) -> str:
        return f"{doc_id}::{stable_hash(section)}::{index:04d}"


class Document(BaseModel):
    """A normalized source document before/after chunking."""

    doc_id: str
    title: str | None = None
    provenance: Provenance
    markdown: str = ""  # normalized, layout-aware Markdown
    raw_meta: dict[str, Any] = Field(default_factory=dict)
    classification: Classification = Field(default_factory=Classification)
    content_hash: str = ""
    created_at: datetime = Field(default_factory=_utcnow)

    @classmethod
    def make_id(cls, file_name: str, content_hash: str) -> str:
        return f"doc_{stable_hash(file_name, content_hash)}"


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float
    rerank_score: float | None = None
