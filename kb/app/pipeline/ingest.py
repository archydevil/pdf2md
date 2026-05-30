"""Ingest orchestrator: parse -> chunk -> enrich -> embed -> store.

Designed to be called from the FastAPI layer (file upload) or directly from the
Meetily bridge (transcripts). Enrichment is optional per-call so you can trade
speed for quality.
"""
from __future__ import annotations

from app.ollama_client import OllamaClient
from app.pipeline.chunk import ChunkConfig, chunk_markdown
from app.pipeline.enrich import Enricher
from app.pipeline.parse import ParseResult
from app.schema import Chunk, Classification, Document, Provenance, SourceKind, stable_hash
from app.store.lancedb_store import KBStore


class IngestResult:
    def __init__(self, doc: Document, n_chunks: int) -> None:
        self.doc = doc
        self.n_chunks = n_chunks


class Ingestor:
    def __init__(
        self,
        store: KBStore | None = None,
        ollama: OllamaClient | None = None,
        enricher: Enricher | None = None,
    ) -> None:
        self.store = store or KBStore()
        self.ollama = ollama or OllamaClient()
        self.enricher = enricher or Enricher(self.ollama)

    async def ingest(
        self,
        parsed: ParseResult,
        file_name: str,
        *,
        classify: bool = True,
        contextualize: bool = True,
        chunk_cfg: ChunkConfig | None = None,
    ) -> IngestResult:
        content_hash = stable_hash(parsed.markdown)
        doc_id = Document.make_id(file_name, content_hash)
        base_prov = Provenance(file_name=file_name, source_kind=parsed.kind)

        doc_class = Classification()
        if classify and parsed.markdown.strip():
            doc_class = await self.enricher.classify(parsed.markdown[:6000])

        doc = Document(
            doc_id=doc_id,
            title=parsed.title,
            provenance=base_prov,
            markdown=parsed.markdown,
            raw_meta=parsed.meta,
            classification=doc_class,
            content_hash=content_hash,
        )

        pieces = chunk_markdown(parsed.markdown, chunk_cfg)
        chunks: list[Chunk] = []
        for piece in pieces:
            section = "/".join(piece.section_path) or "root"
            prov = base_prov.model_copy(update={"section_path": piece.section_path})
            cid = Chunk.make_id(doc_id, section, piece.index)
            prefix = ""
            if contextualize:
                prefix = await self.enricher.contextual_prefix(
                    parsed.title or file_name, doc_class.summary or "", piece.text
                )
            chunk = Chunk(
                id=cid,
                doc_id=doc_id,
                text=piece.text,
                context_prefix=prefix,
                provenance=prov,
                classification=doc_class.model_copy(),
                content_hash=stable_hash(piece.text),
            )
            chunks.append(chunk)

        if chunks:
            vectors = await self.ollama.embed([c.embedding_text() for c in chunks])
            self.store.upsert(chunks, vectors)

        return IngestResult(doc, len(chunks))
