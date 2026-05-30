"""Bridge to Meetily (build-only integration).

Two capabilities are reused:

1. ``import_sqlite`` — read an existing Meetily ``meeting_minutes.sqlite`` and
   turn its transcript chunks (and summaries) into KB documents, preserving
   speaker and timestamps as provenance.
2. ``transcribe`` — a whisper.cpp bridge placeholder so the same large-v3 model
   Meetily uses can produce transcripts for new audio. Wired in Fase 5.

We integrate against the *build* (no source), so the contract is the on-disk
SQLite layout observed in meetily 0.3.1, kept defensive against schema drift.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TranscriptSegment:
    text: str
    speaker: str | None = None
    t_start: float | None = None
    t_end: float | None = None


@dataclass
class MeetingRecord:
    meeting_id: str
    title: str | None
    segments: list[TranscriptSegment] = field(default_factory=list)
    summary_markdown: str | None = None

    def to_markdown(self) -> str:
        lines = [f"# {self.title or self.meeting_id}", ""]
        for seg in self.segments:
            stamp = ""
            if seg.t_start is not None:
                stamp = f"`[{seg.t_start:.1f}s]` "
            who = f"**{seg.speaker}:** " if seg.speaker else ""
            lines.append(f"{stamp}{who}{seg.text}")
        if self.summary_markdown:
            lines += ["", "## Summary (Meetily)", "", self.summary_markdown]
        return "\n".join(lines)


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    try:
        cur = con.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        return set()


def import_sqlite(db_path: str | Path) -> list[MeetingRecord]:
    """Best-effort import of Meetily's SQLite into MeetingRecords.

    Defensive: column names vary across versions, so we probe the schema and
    map the closest available fields.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    records: dict[str, MeetingRecord] = {}

    chunk_cols = _table_columns(con, "transcript_chunks")
    if chunk_cols:
        text_col = "text" if "text" in chunk_cols else next(iter(chunk_cols - {"meeting_id", "id"}), None)
        speaker_col = next((c for c in ("speaker", "speaker_label") if c in chunk_cols), None)
        start_col = next((c for c in ("t_start", "start", "start_time", "ts_start") if c in chunk_cols), None)
        end_col = next((c for c in ("t_end", "end", "end_time", "ts_end") if c in chunk_cols), None)
        order_col = start_col or ("id" if "id" in chunk_cols else None)
        order_sql = f" ORDER BY {order_col}" if order_col else ""
        for row in con.execute(f"SELECT * FROM transcript_chunks{order_sql}"):
            mid = str(row["meeting_id"]) if "meeting_id" in row.keys() else "unknown"
            rec = records.setdefault(mid, MeetingRecord(meeting_id=mid, title=None))
            rec.segments.append(
                TranscriptSegment(
                    text=str(row[text_col]) if text_col else "",
                    speaker=str(row[speaker_col]) if speaker_col and row[speaker_col] is not None else None,
                    t_start=float(row[start_col]) if start_col and row[start_col] is not None else None,
                    t_end=float(row[end_col]) if end_col and row[end_col] is not None else None,
                )
            )

    # Attach summaries if present.
    if _table_columns(con, "summaries"):
        for row in con.execute("SELECT * FROM summaries"):
            mid = str(row["meeting_id"]) if "meeting_id" in row.keys() else None
            if mid and mid in records:
                content = next((row[c] for c in ("content", "summary", "markdown") if c in row.keys()), None)
                if content:
                    records[mid].summary_markdown = str(content)

    con.close()
    return list(records.values())


def transcribe(audio_path: str | Path, model: str = "large-v3") -> list[TranscriptSegment]:
    """whisper.cpp STT bridge — wired in Fase 5.

    Plan: decode with ffmpeg to 16kHz mono WAV, run whisper.cpp (same large-v3
    model Meetily ships), parse segments with timestamps. Raises until enabled.
    """
    raise NotImplementedError(
        "STT whisper.cpp non ancora abilitato (Fase 5). "
        "Serve: ffmpeg + binario whisper.cpp + modello ggml-large-v3."
    )
