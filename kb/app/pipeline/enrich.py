"""LLM-driven enrichment running fully on local Ollama models.

Two operations, both optional but high-impact for weak downstream models:

* ``contextual_prefix`` — Anthropic "Contextual Retrieval": one or two sentences
  that situate a chunk inside its document, prepended before embedding.
* ``classify`` — detailed, filterable metadata (doc_type, taxonomy, topics,
  entities, sensitivity) produced as strict JSON.
"""
from __future__ import annotations

import json

from app.ollama_client import OllamaClient
from app.schema import Classification, Sensitivity

_CTX_SYSTEM = (
    "Sei un assistente che colloca un estratto nel contesto del suo documento. "
    "Rispondi con UNA o DUE frasi, in italiano, che spieghino di cosa tratta "
    "l'estratto e a quale parte del documento appartiene. Niente preamboli."
)

_CLASSIFY_SYSTEM = (
    "Sei un classificatore documentale rigoroso. Restituisci SOLO JSON valido "
    "con le chiavi: lang (ISO 639-1), doc_type, taxonomy (array di percorsi "
    "tipo 'area/sottoarea'), topics (array), entities (oggetto con eventuali "
    "chiavi person, org, date, money, location, email, phone -> array di "
    "stringhe), sensitivity (uno tra public, internal, confidential, "
    "restricted), keywords (array), summary (1 frase). Nessun testo extra."
)


class Enricher:
    def __init__(self, ollama: OllamaClient | None = None) -> None:
        self.ollama = ollama or OllamaClient()

    async def contextual_prefix(self, doc_title: str, doc_summary: str, chunk_text: str) -> str:
        prompt = (
            f"Documento: {doc_title or 'senza titolo'}\n"
            f"Sintesi documento: {doc_summary or 'n/d'}\n\n"
            f"Estratto:\n\"\"\"\n{chunk_text[:2000]}\n\"\"\"\n\n"
            "Contesto (1-2 frasi):"
        )
        try:
            out = await self.ollama.generate(prompt, system=_CTX_SYSTEM, temperature=0.0)
            return out.strip()
        except Exception:
            return ""

    async def classify(self, text: str, model: str | None = None) -> Classification:
        prompt = f"Classifica il seguente testo:\n\"\"\"\n{text[:4000]}\n\"\"\""
        try:
            raw = await self.ollama.generate(
                prompt, system=_CLASSIFY_SYSTEM, temperature=0.0, json_mode=True, model=model
            )
            data = json.loads(raw)
        except Exception:
            return Classification()
        sens = data.get("sensitivity", "internal")
        try:
            sensitivity = Sensitivity(sens)
        except ValueError:
            sensitivity = Sensitivity.internal
        return Classification(
            lang=str(data.get("lang", "und"))[:5],
            doc_type=data.get("doc_type"),
            taxonomy=list(data.get("taxonomy", []) or []),
            topics=list(data.get("topics", []) or []),
            entities={k: list(v) for k, v in (data.get("entities", {}) or {}).items() if v},
            sensitivity=sensitivity,
            keywords=list(data.get("keywords", []) or []),
            summary=data.get("summary"),
        )
