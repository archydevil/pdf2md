"""Lightweight GraphRAG (Fase 6).

Builds an entity/relationship graph from the entities the local LLM already
extracted at ingest time (``chunk.classification.entities``), so no extra LLM
pass is needed. Entities that co-occur in the same chunk are linked; every edge
keeps provenance (the chunk + file it came from).

Query flow: match query terms to graph entities -> expand to neighbours ->
return the connected chunks/facts. This surfaces *relationships* (who is linked
to what) that pure vector search misses, while staying fully local.

The graph is persisted as JSON under ``data_dir/graph.json`` for air-gap
portability and easy inspection.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from app.config import get_settings
from app.store.lancedb_store import KBStore

# Entity categories worth linking (skip noisy/low-signal buckets).
_USEFUL_TYPES = {"person", "org", "organization", "location", "product", "project", "event", "money", "date"}
_MIN_LEN = 2


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _key(value: str) -> str:
    return _norm(value).lower()


@dataclass
class GraphNode:
    name: str
    type: str
    count: int = 0
    chunk_ids: set[str] = field(default_factory=set)


@dataclass
class GraphEdge:
    source: str
    target: str
    weight: int = 0
    chunk_ids: set[str] = field(default_factory=set)


@dataclass
class KnowledgeGraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: dict[tuple[str, str], GraphEdge] = field(default_factory=dict)
    # entity key -> set of chunk ids (for retrieval)
    chunk_index: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    # --- serialization ---------------------------------------------------- #
    def to_dict(self) -> dict:
        return {
            "nodes": [
                {"key": k, "name": n.name, "type": n.type, "count": n.count, "chunk_ids": sorted(n.chunk_ids)}
                for k, n in self.nodes.items()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "weight": e.weight, "chunk_ids": sorted(e.chunk_ids)}
                for e in self.edges.values()
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeGraph":
        g = cls()
        for n in data.get("nodes", []):
            node = GraphNode(name=n["name"], type=n["type"], count=n.get("count", 0), chunk_ids=set(n.get("chunk_ids", [])))
            g.nodes[n["key"]] = node
            for cid in node.chunk_ids:
                g.chunk_index[n["key"]].add(cid)
        for e in data.get("edges", []):
            key = (e["source"], e["target"])
            g.edges[key] = GraphEdge(source=e["source"], target=e["target"], weight=e.get("weight", 0), chunk_ids=set(e.get("chunk_ids", [])))
        return g

    # --- query ------------------------------------------------------------ #
    def neighbors(self, key: str) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        for (s, t), e in self.edges.items():
            if s == key:
                out.append((t, e.weight))
            elif t == key:
                out.append((s, e.weight))
        out.sort(key=lambda kv: kv[1], reverse=True)
        return out

    def match_entities(self, query: str) -> list[str]:
        """Return entity keys whose name appears in / overlaps the query."""
        q = _key(query)
        hits: list[tuple[str, int]] = []
        for key, node in self.nodes.items():
            if key and key in q:
                hits.append((key, node.count))
        hits.sort(key=lambda kv: (len(kv[0]), kv[1]), reverse=True)
        return [k for k, _ in hits]


def _path() -> Path:
    return get_settings().data_dir / "graph.json"


def build_graph(store: KBStore | None = None) -> KnowledgeGraph:
    """Build the graph from stored chunks and persist it."""
    store = store or KBStore()
    graph = KnowledgeGraph()
    for chunk in store.all_chunks():
        entities = chunk.classification.entities or {}
        present: list[tuple[str, str]] = []  # (key, name)
        for etype, values in entities.items():
            if etype.lower() not in _USEFUL_TYPES:
                continue
            for raw in values:
                name = _norm(str(raw))
                if len(name) < _MIN_LEN:
                    continue
                key = _key(name)
                node = graph.nodes.get(key)
                if node is None:
                    node = GraphNode(name=name, type=etype.lower())
                    graph.nodes[key] = node
                node.count += 1
                node.chunk_ids.add(chunk.id)
                graph.chunk_index[key].add(chunk.id)
                present.append((key, name))
        # Link entities co-occurring in the same chunk.
        for (ka, _), (kb, _) in combinations(present, 2):
            if ka == kb:
                continue
            ekey = tuple(sorted((ka, kb)))  # type: ignore[assignment]
            edge = graph.edges.get(ekey)  # type: ignore[arg-type]
            if edge is None:
                edge = GraphEdge(source=ekey[0], target=ekey[1])
                graph.edges[ekey] = edge  # type: ignore[index]
            edge.weight += 1
            edge.chunk_ids.add(chunk.id)
    _path().write_text(json.dumps(graph.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return graph


def load_graph() -> KnowledgeGraph | None:
    p = _path()
    if not p.exists():
        return None
    return KnowledgeGraph.from_dict(json.loads(p.read_text(encoding="utf-8")))


def query_graph(query: str, hops: int = 1, graph: KnowledgeGraph | None = None) -> dict:
    """Return matched entities, their neighbourhood and the connecting chunks."""
    graph = graph or load_graph()
    if graph is None:
        return {"matched": [], "related": [], "chunk_ids": [], "built": False}

    matched = graph.match_entities(query)
    seen: set[str] = set(matched)
    frontier = list(matched)
    related: list[dict] = []
    for _ in range(max(0, hops)):
        next_frontier: list[str] = []
        for key in frontier:
            for nbr_key, weight in graph.neighbors(key):
                node = graph.nodes.get(nbr_key)
                if node is None:
                    continue
                if nbr_key not in seen:
                    seen.add(nbr_key)
                    next_frontier.append(nbr_key)
                related.append({"from": graph.nodes[key].name, "to": node.name, "type": node.type, "weight": weight})
        frontier = next_frontier

    chunk_ids: set[str] = set()
    for key in seen:
        chunk_ids |= graph.chunk_index.get(key, set())

    matched_names = [graph.nodes[k].name for k in matched if k in graph.nodes]
    # Deduplicate related edges keeping max weight.
    dedup: dict[tuple[str, str], dict] = {}
    for r in related:
        k = (r["from"], r["to"])
        if k not in dedup or r["weight"] > dedup[k]["weight"]:
            dedup[k] = r
    return {
        "matched": matched_names,
        "related": sorted(dedup.values(), key=lambda r: r["weight"], reverse=True),
        "chunk_ids": sorted(chunk_ids),
        "built": True,
    }
