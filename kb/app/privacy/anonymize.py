"""Reversible PII anonymization (Microsoft Presidio + spaCy IT).

Air-gap rule: text that may leave the machine (cloud egress) MUST first pass
through ``anonymize``. A reversible mapping (placeholder -> original) is kept in
memory so that responses coming back from the cloud can be ``deanonymize``-d.

Presidio/spaCy are heavy and optional; when they are not installed we fall back
to a conservative regex detector so the egress gateway still has *something* to
redact (better deny-ish than leak), and we clearly flag degraded mode.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from functools import lru_cache

# Conservative fallback patterns (used only when Presidio is unavailable).
_FALLBACK_PATTERNS: dict[str, re.Pattern[str]] = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "PHONE": re.compile(r"(?<!\d)(?:\+?\d[\d .\-]{7,}\d)(?!\d)"),
    "IBAN": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "CF": re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}


@dataclass
class AnonymizationResult:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)  # placeholder -> original
    entities: list[dict] = field(default_factory=list)
    degraded: bool = False  # True when running on the regex fallback

    def deanonymize(self, text: str) -> str:
        for placeholder, original in self.mapping.items():
            text = text.replace(placeholder, original)
        return text


def _placeholder(label: str) -> str:
    return f"[[{label}_{uuid.uuid4().hex[:8]}]]"


def _drop_overlaps(results: list) -> list:  # noqa: ANN001 - presidio RecognizerResult
    """Keep only non-overlapping spans, preferring higher score then longer.

    Presidio can return overlapping detections (e.g. EMAIL_ADDRESS + URL over
    the same substring). Replacing overlapping spans corrupts the text and
    breaks reversibility, so we greedily select a non-overlapping subset.
    """
    ordered = sorted(results, key=lambda r: (r.score, r.end - r.start), reverse=True)
    kept: list = []
    for r in ordered:
        if any(not (r.end <= k.start or r.start >= k.end) for k in kept):
            continue
        kept.append(r)
    return kept


@lru_cache(maxsize=4)
def _build_analyzer(language: str):  # noqa: ANN202 - presidio types are optional
    """Build (and cache) a Presidio analyzer wired to a spaCy model.

    The default ``AnalyzerEngine()`` only knows English (``en_core_web_lg``).
    For Italian we point the NLP engine at ``it_core_news_sm`` and register the
    Italian predefined recognizers (fiscal code, VAT, etc.).
    """
    from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]
    from presidio_analyzer.nlp_engine import (  # type: ignore[import-not-found]
        NlpEngineProvider,
    )

    spacy_model = "it_core_news_sm" if language == "it" else "en_core_web_lg"
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": language, "model_name": spacy_model}],
        }
    )
    nlp_engine = provider.create_engine()
    return AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=[language])


def _try_presidio(text: str, language: str) -> AnonymizationResult | None:
    try:
        analyzer = _build_analyzer(language)
    except Exception:
        return None

    results = analyzer.analyze(text=text, language=language)
    results = _drop_overlaps(results)
    results = sorted(results, key=lambda r: r.start, reverse=True)
    mapping: dict[str, str] = {}
    entities: list[dict] = []
    out = text
    for r in results:
        original = text[r.start : r.end]
        placeholder = _placeholder(r.entity_type)
        mapping[placeholder] = original
        entities.append({"type": r.entity_type, "score": r.score, "start": r.start, "end": r.end})
        out = out[: r.start] + placeholder + out[r.end :]
    return AnonymizationResult(text=out, mapping=mapping, entities=entities, degraded=False)


def _fallback(text: str) -> AnonymizationResult:
    mapping: dict[str, str] = {}
    entities: list[dict] = []
    out = text
    for label, pattern in _FALLBACK_PATTERNS.items():
        for match in pattern.finditer(text):
            original = match.group(0)
            if original in mapping.values():
                continue
            placeholder = _placeholder(label)
            mapping[placeholder] = original
            entities.append({"type": label, "score": 0.5, "start": match.start(), "end": match.end()})
            out = out.replace(original, placeholder)
    return AnonymizationResult(text=out, mapping=mapping, entities=entities, degraded=True)


def anonymize(text: str, language: str = "it") -> AnonymizationResult:
    """Return a reversible anonymization of ``text``.

    Prefers Presidio; falls back to regex with ``degraded=True`` flagged.
    """
    result = _try_presidio(text, language)
    if result is not None:
        return result
    return _fallback(text)
