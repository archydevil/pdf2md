"""STT + parsing unit tests (no audio decoding, no Ollama)."""
from __future__ import annotations

from pathlib import Path

from app.bridges.stt import STTSegment, segments_to_markdown
from app.pipeline.parse import _html_to_markdown, detect_kind, parse_markdown
from app.schema import SourceKind


def test_segments_to_markdown_formats_timestamps():
    segs = [
        STTSegment(text="Ciao a tutti", t_start=0.0, t_end=2.0),
        STTSegment(text="Secondo punto", t_start=65.0, t_end=70.0),
        STTSegment(text="", t_start=80.0, t_end=81.0),  # empty -> skipped
    ]
    md = segments_to_markdown(segs, "Riunione")
    assert md.startswith("# Riunione")
    assert "[00:00] Ciao a tutti" in md
    assert "[01:05] Secondo punto" in md
    # Empty segment must not appear.
    assert "[01:20]" not in md


def test_detect_kind_maps_extensions():
    assert detect_kind(Path("a.png")) is SourceKind.image
    assert detect_kind(Path("a.PDF")) is SourceKind.pdf
    assert detect_kind(Path("a.md")) is SourceKind.markdown
    assert detect_kind(Path("a.unknown")) is SourceKind.other


def test_html_to_markdown_strips_tags():
    out = _html_to_markdown("<h1>Titolo</h1><p>Ciao <b>mondo</b></p><script>x()</script>")
    assert "# Titolo" in out
    assert "Ciao" in out
    assert "x()" not in out  # script content removed
    assert "<" not in out  # no leftover tags


def test_parse_markdown_preserves_content():
    res = parse_markdown("# H\n\nbody", "T", SourceKind.markdown)
    assert res.markdown == "# H\n\nbody"
    assert res.kind is SourceKind.markdown
    assert res.meta["parser"] == "external"
