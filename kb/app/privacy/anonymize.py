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


def _try_presidio(text: str, language: str) -> AnonymizationResult | None:
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]
    except Exception:
        return None

    analyzer = AnalyzerEngine()
    results = analyzer.analyze(text=text, language=language)
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
