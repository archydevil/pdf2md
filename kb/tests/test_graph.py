"""GraphRAG unit tests — graph construction + query over synthetic chunks."""
from __future__ import annotations

from app.pipeline import graph as graphmod
from app.pipeline.graph import build_graph, query_graph
from app.schema import Chunk, Classification, Provenance, SourceKind


class _FakeStore:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks

    def all_chunks(self) -> list[Chunk]:
        return self._chunks


def _chunk(cid: str, entities: dict[str, list[str]]) -> Chunk:
    return Chunk(
        id=cid,
        doc_id="doc1",
        text="x",
        provenance=Provenance(file_name="f.md", source_kind=SourceKind.markdown),
        classification=Classification(entities=entities),
    )


def test_build_graph_links_cooccurring_entities(tmp_path, monkeypatch):
    monkeypatch.setattr(graphmod, "_path", lambda: tmp_path / "graph.json")
    store = _FakeStore(
        [
            _chunk("c1", {"person": ["Mario Rossi", "Laura Bianchi"], "org": ["Acme Corp"]}),
            _chunk("c2", {"person": ["Laura Bianchi"], "org": ["Acme Corp", "Beta Srl"]}),
        ]
    )
    g = build_graph(store)  # type: ignore[arg-type]

    # 4 distinct entities -> 4 nodes.
    assert len(g.nodes) == 4
    # Laura Bianchi + Acme Corp co-occur in BOTH chunks -> weight 2.
    res = query_graph("Laura Bianchi", hops=1, graph=g)
    assert "Laura Bianchi" in res["matched"]
    rel = {(r["from"], r["to"]): r["weight"] for r in res["related"]}
    assert rel.get(("Laura Bianchi", "Acme Corp")) == 2
    # Provenance: both chunk ids surface.
    assert set(res["chunk_ids"]) == {"c1", "c2"}


def test_query_graph_filters_noise_types(tmp_path, monkeypatch):
    monkeypatch.setattr(graphmod, "_path", lambda: tmp_path / "graph.json")
    store = _FakeStore([_chunk("c1", {"keyword": ["foo"], "misc": ["bar"]})])
    g = build_graph(store)  # type: ignore[arg-type]
    # Only noise types -> no graph nodes.
    assert len(g.nodes) == 0


def test_query_graph_unbuilt_returns_built_false(tmp_path, monkeypatch):
    monkeypatch.setattr(graphmod, "_path", lambda: tmp_path / "missing.json")
    res = query_graph("anything", hops=1)
    assert res["built"] is False
    assert res["matched"] == []


def test_match_entities_is_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.setattr(graphmod, "_path", lambda: tmp_path / "graph.json")
    store = _FakeStore([_chunk("c1", {"org": ["Acme Corp"], "person": ["Mario Rossi"]})])
    g = build_graph(store)  # type: ignore[arg-type]
    res = query_graph("parlami di acme corp", hops=1, graph=g)
    assert "Acme Corp" in res["matched"]
