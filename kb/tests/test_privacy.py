"""Privacy / anonymization unit tests.

These avoid forcing Presidio: they exercise the regex fallback (always present)
and the overlap-resolution helper that guarantees reversibility.
"""
from __future__ import annotations

from app.privacy import anonymize as anon
from app.privacy.anonymize import _drop_overlaps, _fallback, anonymize


class _Span:
    def __init__(self, start: int, end: int, score: float) -> None:
        self.start = start
        self.end = end
        self.score = score


def test_drop_overlaps_keeps_higher_score():
    spans = [_Span(0, 10, 0.6), _Span(5, 15, 0.9), _Span(20, 25, 0.5)]
    kept = _drop_overlaps(spans)
    # The 0.6 span overlaps the 0.9 span -> dropped; non-overlapping 0.5 kept.
    kept_spans = {(s.start, s.end) for s in kept}
    assert (5, 15) in kept_spans
    assert (20, 25) in kept_spans
    assert (0, 10) not in kept_spans


def test_fallback_is_reversible():
    text = "Scrivi a mario.rossi@example.com oppure IBAN IT60X0542811101000000123456."
    result = _fallback(text)
    assert result.degraded is True
    assert result.mapping  # something was redacted
    # No original PII left in the anonymized text.
    assert "mario.rossi@example.com" not in result.text
    # Reversible round-trip.
    assert result.deanonymize(result.text) == text


def test_anonymize_falls_back_when_presidio_missing(monkeypatch):
    # Force the Presidio path to be unavailable -> guaranteed regex fallback.
    monkeypatch.setattr(anon, "_try_presidio", lambda text, language: None)
    result = anonymize("Email test@example.com", language="it")
    assert result.degraded is True
    assert "test@example.com" not in result.text
    assert result.deanonymize(result.text) == "Email test@example.com"
