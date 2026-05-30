"""Egress gateway — the single choke point for anything leaving the machine.

Policy (air-gap by default):
  * If ``allow_cloud_egress`` is False, ALL egress is denied. Hard stop.
  * If True, the payload MUST be anonymized first. The gateway anonymizes,
    optionally requires manual approval (review the diff), sends, then
    de-anonymizes the response with the reversible mapping.

This keeps the "cloud only after anonymization + manual review" guarantee in one
auditable place instead of scattered across call sites.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.privacy.anonymize import AnonymizationResult, anonymize


class EgressDenied(RuntimeError):
    """Raised when egress is attempted while air-gap is active."""


@dataclass
class EgressEnvelope:
    safe_text: str
    anonymization: AnonymizationResult
    approved: bool

    def restore(self, response_text: str) -> str:
        """Map placeholders in a cloud response back to the original values."""
        return self.anonymization.deanonymize(response_text)


def prepare_egress(text: str, language: str = "it", require_approval: bool = True) -> EgressEnvelope:
    """Validate and anonymize ``text`` before it can leave the machine.

    Raises ``EgressDenied`` when the air-gap switch is on. Otherwise returns an
    envelope with anonymized text. When ``require_approval`` is True the caller
    must flip ``approved`` (after reviewing ``anonymization``) before sending.
    """
    settings = get_settings()
    if not settings.allow_cloud_egress:
        raise EgressDenied(
            "Egress verso il cloud disabilitato (air-gap). "
            "Imposta KB_ALLOW_CLOUD_EGRESS=true per consentirlo."
        )
    result = anonymize(text, language=language)
    return EgressEnvelope(
        safe_text=result.text,
        anonymization=result,
        approved=not require_approval,
    )
