"""Parse heterogeneous inputs into normalized, layout-aware Markdown.

Fase 0 handles text/markdown/html natively (no heavy deps). PDF and DOCX use
Docling when available (best layout/table/reading-order fidelity) and degrade
gracefully otherwise so the sidecar always imports and runs.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from app.schema import SourceKind

_EXT_KIND = {
    ".pdf": SourceKind.pdf,
    ".docx": SourceKind.docx,
    ".txt": SourceKind.text,
    ".md": SourceKind.markdown,
    ".markdown": SourceKind.markdown,
    ".html": SourceKind.html,
    ".htm": SourceKind.html,
    ".eml": SourceKind.email,
}


def detect_kind(path: Path) -> SourceKind:
    return _EXT_KIND.get(path.suffix.lower(), SourceKind.other)


def _html_to_markdown(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)<h([1-6])[^>]*>(.*?)</h\1>", lambda m: f"\n{'#' * int(m.group(1))} {m.group(2)}\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    return html.unescape(text).strip()


class ParseResult:
    def __init__(self, markdown: str, kind: SourceKind, title: str | None, meta: dict) -> None:
        self.markdown = markdown
        self.kind = kind
        self.title = title
        self.meta = meta


def parse_file(path: Path) -> ParseResult:
    kind = detect_kind(path)
    suffix = path.suffix.lower()
    title = path.stem
    meta: dict = {}

    if suffix in {".txt", ".md", ".markdown"}:
        return ParseResult(path.read_text(encoding="utf-8", errors="replace"), kind, title, meta)

    if suffix in {".html", ".htm", ".eml"}:
        raw = path.read_text(encoding="utf-8", errors="replace")
        return ParseResult(_html_to_markdown(raw), kind, title, meta)

    if suffix in {".pdf", ".docx"}:
        md = _parse_with_docling(path)
        if md is not None:
            return ParseResult(md, kind, title, {"parser": "docling"})
        # Fallback: signal that a layout-aware parser is required.
        raise RuntimeError(
            f"Per {suffix} serve Docling. Installa con: pip install docling "
            "(oppure invia il Markdown gia' convertito dall'UI pdf2md)."
        )

    # Unknown: best-effort plain read.
    return ParseResult(path.read_text(encoding="utf-8", errors="replace"), kind, title, meta)


def parse_markdown(markdown: str, title: str | None, kind: SourceKind) -> ParseResult:
    """Entry point for content already converted to Markdown (e.g. by pdf2md)."""
    return ParseResult(markdown, kind, title, {"parser": "external"})


def _parse_with_docling(path: Path) -> str | None:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except Exception:
        return None
    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
        return result.document.export_to_markdown()
    except Exception:
        return None
