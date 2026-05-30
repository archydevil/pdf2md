"""MCP server exposing the Knowledge Base as tools (Fase 6).

Runs over stdio so any MCP client (VS Code, Claude Desktop, custom agents) can
search, chat with citations, ingest content and query the entity graph — fully
local. Reuses the exact same pipeline as the FastAPI sidecar.

Run:
    python -m app.mcp_server

VS Code (.vscode/mcp.json) / Claude Desktop config:
    {
      "command": "/abs/path/kb/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/abs/path/kb"
    }
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.ollama_client import OllamaClient
from app.pipeline.chat import ChatEngine
from app.pipeline.graph import build_graph, query_graph
from app.pipeline.ingest import Ingestor
from app.pipeline.parse import parse_markdown
from app.pipeline.retrieve import Retriever
from app.schema import SourceKind
from app.store.lancedb_store import KBStore

mcp = FastMCP("kb-forge")

_store = KBStore()
_ollama = OllamaClient()
_ingestor = Ingestor(store=_store, ollama=_ollama)
_retriever = Retriever(store=_store, ollama=_ollama)
_chat = ChatEngine(retriever=_retriever, ollama=_ollama)


@mcp.tool()
async def kb_search(query: str, k: int = 6, rerank: bool = False) -> list[dict]:
    """Hybrid search over the knowledge base. Returns ranked chunks with citations."""
    hits = await _retriever.search(query, k=k, rerank=rerank)
    return [
        {
            "text": h.chunk.text,
            "file_name": h.chunk.provenance.file_name,
            "section_path": h.chunk.provenance.section_path,
            "page": h.chunk.provenance.page,
            "score": h.score,
        }
        for h in hits
    ]


@mcp.tool()
async def kb_chat(query: str, k: int = 6, rerank: bool = False) -> dict:
    """Answer a question grounded ONLY in the knowledge base, with [n] citations."""
    result = await _chat.answer(query, k=k, rerank=rerank)
    return {
        "answer": result.answer,
        "citations": [
            {"n": c.n, "file_name": c.file_name, "section_path": c.section_path, "page": c.page}
            for c in result.citations
        ],
    }


@mcp.tool()
async def kb_ingest_markdown(markdown: str, file_name: str, title: str | None = None) -> dict:
    """Ingest Markdown content into the knowledge base (classify + embed + index)."""
    parsed = parse_markdown(markdown, title, SourceKind.markdown)
    result = await _ingestor.ingest(parsed, file_name, classify=True, contextualize=True)
    return {"doc_id": result.doc.doc_id, "chunks": result.n_chunks}


@mcp.tool()
def kb_stats() -> dict:
    """Return knowledge base size and storage location."""
    return {"chunks": _store.count(), "lancedb_dir": str(get_settings().lancedb_dir)}


@mcp.tool()
def kb_graph_build() -> dict:
    """(Re)build the entity-relationship graph from stored chunks."""
    graph = build_graph(_store)
    return {"nodes": len(graph.nodes), "edges": len(graph.edges)}


@mcp.tool()
def kb_graph_query(query: str, hops: int = 1) -> dict:
    """Query the entity graph: matched entities, their relations and source chunks."""
    return query_graph(query, hops=hops)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
