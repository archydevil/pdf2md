"""FastAPI entry point for the KB Forge sidecar.

Endpoints (Fase 0/1):
  GET  /health                 - sidecar + Ollama status
  GET  /stats                  - KB size
  POST /ingest/markdown        - ingest content already converted (e.g. pdf2md)
  POST /ingest/file            - upload a file (txt/md/html; pdf/docx via Docling)
  POST /search                 - hybrid retrieval with citations
  GET  /analysis/templates     - list Meetily-derived analysis templates
  POST /analysis/run           - run a template over given content
  POST /meetily/import         - import a Meetily meeting_minutes.sqlite
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.analysis.engine import AnalysisEngine, list_templates
from app.bridges.meetily import import_sqlite
from app.config import get_settings
from app.ollama_client import OllamaClient
from app.pipeline.chat import ChatEngine
from app.pipeline.ingest import Ingestor
from app.pipeline.parse import parse_file_async, parse_markdown
from app.pipeline.retrieve import Retriever
from app.privacy.anonymize import anonymize
from app.privacy.egress import EgressDenied, prepare_egress
from app.schema import SourceKind
from app.store.lancedb_store import KBStore

app = FastAPI(title="KB Forge", version="0.1.0")

# Local-only UI (Next.js dev on 3000 / Electron). Air-gap friendly: localhost only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "app://.",  # Electron packaged origin
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_store = KBStore()
_ollama = OllamaClient()
_ingestor = Ingestor(store=_store, ollama=_ollama)
_retriever = Retriever(store=_store, ollama=_ollama)
_analysis = AnalysisEngine(ollama=_ollama)
_chat = ChatEngine(retriever=_retriever, ollama=_ollama)


class IngestMarkdownBody(BaseModel):
    markdown: str
    file_name: str
    title: str | None = None
    classify: bool = True
    contextualize: bool = True


class SearchBody(BaseModel):
    query: str
    k: int = 8
    where: str | None = None
    rerank: bool | None = None


class ChatBody(BaseModel):
    query: str
    k: int = 6
    where: str | None = None
    rerank: bool | None = None
    model: str | None = None


class AnalysisBody(BaseModel):
    content: str
    template_id: str
    model: str | None = None


class MeetilyImportBody(BaseModel):
    db_path: str
    classify: bool = True
    contextualize: bool = False


class AnonymizeBody(BaseModel):
    text: str
    language: str = "it"


class EgressBody(BaseModel):
    text: str
    language: str = "it"
    require_approval: bool = True


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "ollama": await _ollama.health(), "model": get_settings().llm_model}


@app.get("/stats")
async def stats() -> dict:
    return {"chunks": _store.count(), "lancedb_dir": str(get_settings().lancedb_dir)}


@app.post("/ingest/markdown")
async def ingest_markdown(body: IngestMarkdownBody) -> dict:
    parsed = parse_markdown(body.markdown, body.title, SourceKind.markdown)
    result = await _ingestor.ingest(
        parsed, body.file_name, classify=body.classify, contextualize=body.contextualize
    )
    return {"doc_id": result.doc.doc_id, "chunks": result.n_chunks}


@app.post("/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    classify: bool = Form(True),
    contextualize: bool = Form(True),
) -> dict:
    suffix = Path(file.filename or "upload").suffix
    with tempfile.NamedTemporaryFile(delete=True, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp.flush()
        try:
            parsed = parse_file_async(Path(tmp.name))
            parsed = await parsed
        except RuntimeError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
    result = await _ingestor.ingest(
        parsed, file.filename or "upload", classify=classify, contextualize=contextualize
    )
    return {"doc_id": result.doc.doc_id, "chunks": result.n_chunks}


@app.post("/search")
async def search(body: SearchBody) -> dict:
    hits = await _retriever.search(body.query, k=body.k, where=body.where, rerank=body.rerank)
    return {
        "query": body.query,
        "results": [
            {
                "id": h.chunk.id,
                "score": h.score,
                "rerank_score": h.rerank_score,
                "text": h.chunk.text,
                "context": h.chunk.context_prefix,
                "source": h.chunk.provenance.model_dump(),
                "classification": h.chunk.classification.model_dump(),
            }
            for h in hits
        ],
    }


@app.post("/chat")
async def chat(body: ChatBody) -> dict:
    result = await _chat.answer(
        body.query, k=body.k, where=body.where, rerank=body.rerank, model=body.model
    )
    return {
        "query": body.query,
        "answer": result.answer,
        "citations": [
            {
                "n": c.n,
                "chunk_id": c.chunk_id,
                "file_name": c.file_name,
                "section_path": c.section_path,
                "page": c.page,
                "text": c.text,
            }
            for c in result.citations
        ],
    }


@app.get("/analysis/templates")
async def analysis_templates() -> dict:
    return {"templates": list_templates()}


@app.post("/analysis/run")
async def analysis_run(body: AnalysisBody) -> dict:
    try:
        markdown = await _analysis.analyze(body.content, body.template_id, model=body.model)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"template_id": body.template_id, "markdown": markdown}


@app.post("/meetily/import")
async def meetily_import(body: MeetilyImportBody) -> dict:
    try:
        meetings = import_sqlite(body.db_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    imported = []
    for meeting in meetings:
        parsed = parse_markdown(meeting.to_markdown(), meeting.title or meeting.meeting_id, SourceKind.transcript)
        result = await _ingestor.ingest(
            parsed,
            f"meetily_{meeting.meeting_id}.md",
            classify=body.classify,
            contextualize=body.contextualize,
        )
        imported.append({"meeting_id": meeting.meeting_id, "chunks": result.n_chunks})
    return {"meetings": imported}


@app.post("/privacy/anonymize")
async def privacy_anonymize(body: AnonymizeBody) -> dict:
    result = anonymize(body.text, language=body.language)
    return {
        "text": result.text,
        "degraded": result.degraded,
        "entities": result.entities,
        "n_redacted": len(result.mapping),
    }


@app.post("/privacy/egress/preview")
async def privacy_egress_preview(body: EgressBody) -> dict:
    """Anonymize + validate egress without sending anything.

    Returns 403 when the air-gap switch is on (KB_ALLOW_CLOUD_EGRESS=false).
    """
    try:
        envelope = prepare_egress(
            body.text, language=body.language, require_approval=body.require_approval
        )
    except EgressDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {
        "safe_text": envelope.safe_text,
        "approved": envelope.approved,
        "degraded": envelope.anonymization.degraded,
        "n_redacted": len(envelope.anonymization.mapping),
    }

