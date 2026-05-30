"""Schema invariants: stable IDs, dedup hashing, embedding text."""
from __future__ import annotations

from app.schema import Chunk, Provenance, SourceKind, stable_hash


def test_stable_hash_is_deterministic():
    assert stable_hash("a", "b") == stable_hash("a", "b")
    assert stable_hash("a", "b") != stable_hash("b", "a")
    assert len(stable_hash("x")) == 16


def test_make_id_is_stable_and_indexed():
    a = Chunk.make_id("doc1", "Sezione 1", 0)
    b = Chunk.make_id("doc1", "Sezione 1", 0)
    c = Chunk.make_id("doc1", "Sezione 1", 1)
    assert a == b
    assert a != c
    assert a.endswith("0000")
    assert c.endswith("0001")


def test_embedding_text_prepends_context_prefix():
    ch = Chunk(
        id="i",
        doc_id="d",
        text="contenuto",
        context_prefix="contesto",
        provenance=Provenance(file_name="f.md", source_kind=SourceKind.markdown),
    )
    assert ch.embedding_text() == "contesto\n\ncontenuto"


def test_embedding_text_without_prefix_is_plain_text():
    ch = Chunk(
        id="i",
        doc_id="d",
        text="solo testo",
        provenance=Provenance(file_name="f.md", source_kind=SourceKind.markdown),
    )
    assert ch.embedding_text() == "solo testo"
