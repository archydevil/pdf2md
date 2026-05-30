"""Structure-aware chunking over normalized Markdown.

Strategy:
  1. Split by Markdown headings to keep semantic sections intact.
  2. Within a section, pack paragraphs into token-bounded windows with overlap.
  3. Track the heading path so each chunk carries its section provenance.

A lightweight word-based token estimate is used to stay dependency-free; swap in
a real tokenizer later if you need exact budgets.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def estimate_tokens(text: str) -> int:
    # ~0.75 words per token for mixed IT/EN; good enough for windowing.
    return max(1, int(len(text.split()) / 0.75))


@dataclass
class Section:
    path: list[str]
    text: str = ""


@dataclass
class ChunkPiece:
    text: str
    section_path: list[str]
    index: int
    char_start: int
    char_end: int


@dataclass
class ChunkConfig:
    max_tokens: int = 400
    overlap_tokens: int = 60
    min_tokens: int = 40


def split_sections(markdown: str) -> list[Section]:
    sections: list[Section] = []
    stack: list[str] = []
    current = Section(path=[])
    for line in markdown.splitlines():
        m = _HEADING.match(line)
        if m:
            if current.text.strip():
                sections.append(current)
            level = len(m.group(1))
            title = m.group(2).strip()
            stack = stack[: level - 1]
            stack.append(title)
            current = Section(path=list(stack))
        else:
            current.text += line + "\n"
    if current.text.strip():
        sections.append(current)
    return sections or [Section(path=[], text=markdown)]


def _pack(section: Section, cfg: ChunkConfig, start_index: int) -> list[ChunkPiece]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section.text) if p.strip()]
    pieces: list[ChunkPiece] = []
    buf: list[str] = []
    buf_tokens = 0
    index = start_index
    for para in paragraphs:
        ptok = estimate_tokens(para)
        if buf_tokens + ptok > cfg.max_tokens and buf:
            text = "\n\n".join(buf)
            pieces.append(ChunkPiece(text, section.path, index, 0, len(text)))
            index += 1
            # overlap: keep tail paragraphs up to overlap budget
            tail: list[str] = []
            tok = 0
            for p in reversed(buf):
                tok += estimate_tokens(p)
                tail.insert(0, p)
                if tok >= cfg.overlap_tokens:
                    break
            buf = tail
            buf_tokens = sum(estimate_tokens(p) for p in buf)
        buf.append(para)
        buf_tokens += ptok
    if buf:
        text = "\n\n".join(buf)
        if estimate_tokens(text) >= cfg.min_tokens or not pieces:
            pieces.append(ChunkPiece(text, section.path, index, 0, len(text)))
    return pieces


def chunk_markdown(markdown: str, cfg: ChunkConfig | None = None) -> list[ChunkPiece]:
    cfg = cfg or ChunkConfig()
    pieces: list[ChunkPiece] = []
    idx = 0
    for section in split_sections(markdown):
        section_pieces = _pack(section, cfg, idx)
        pieces.extend(section_pieces)
        idx += len(section_pieces)
    return pieces
