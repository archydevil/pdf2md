"""Cloud routing tests for the chat engine.

No network: the cloud client is monkeypatched. These verify the egress policy
(air-gap switch + reversible anonymization) around the cloud provider path.
"""
from __future__ import annotations

import asyncio

import pytest

from app.config import get_settings
from app.pipeline import chat as chatmod
from app.privacy.egress import EgressDenied


def _engine_with_stub_cloud(captured: dict):
    engine = chatmod.ChatEngine.__new__(chatmod.ChatEngine)

    class _StubCloud:
        async def generate(self, prompt, *, system=None, model=None, temperature=0.0):
            captured["sent"] = prompt
            # Echo a placeholder back so we can check de-anonymization.
            return f"Risposta su {prompt.split()[-1]}"

    engine.cloud = _StubCloud()
    return engine


def _reset_settings():
    get_settings.cache_clear()


def test_cloud_denied_when_airgap(monkeypatch):
    _reset_settings()
    monkeypatch.setenv("KB_ALLOW_CLOUD_EGRESS", "false")
    monkeypatch.setenv("KB_CLOUD_ANONYMIZE", "true")
    _reset_settings()
    engine = _engine_with_stub_cloud({})
    with pytest.raises(EgressDenied):
        asyncio.run(engine._answer_cloud("Chi e Mario Rossi?"))
    _reset_settings()


def test_cloud_anonymizes_before_send_and_restores(monkeypatch):
    _reset_settings()
    monkeypatch.setenv("KB_ALLOW_CLOUD_EGRESS", "true")
    monkeypatch.setenv("KB_CLOUD_ANONYMIZE", "true")
    _reset_settings()
    captured: dict = {}
    engine = _engine_with_stub_cloud(captured)
    out = asyncio.run(engine._answer_cloud("Scrivi a mario.rossi@example.com"))
    # The raw email must NOT have left the machine.
    assert "mario.rossi@example.com" not in captured["sent"]
    # The de-anonymized answer restores the original value.
    assert "mario.rossi@example.com" in out
    _reset_settings()


def test_cloud_raw_when_anonymize_disabled(monkeypatch):
    _reset_settings()
    monkeypatch.setenv("KB_ALLOW_CLOUD_EGRESS", "true")
    monkeypatch.setenv("KB_CLOUD_ANONYMIZE", "false")
    _reset_settings()
    captured: dict = {}
    engine = _engine_with_stub_cloud(captured)
    asyncio.run(engine._answer_cloud("Domanda semplice"))
    # Anonymization off -> prompt sent verbatim.
    assert captured["sent"] == "Domanda semplice"
    _reset_settings()


def test_per_request_api_key_is_explicit_consent(monkeypatch):
    # Air-gap is ON, but supplying an API key for the request grants consent.
    _reset_settings()
    monkeypatch.setenv("KB_ALLOW_CLOUD_EGRESS", "false")
    monkeypatch.setenv("KB_CLOUD_ANONYMIZE", "true")
    _reset_settings()
    captured: dict = {}
    engine = chatmod.ChatEngine.__new__(chatmod.ChatEngine)

    class _StubCloud:
        async def generate(self, prompt, *, system=None, model=None, temperature=0.0):
            captured["sent"] = prompt
            return "ok"

    # No env-configured client; per-request key drives a fresh CloudClient.
    monkeypatch.setattr(chatmod, "CloudClient", lambda **kw: _StubCloud())
    engine.cloud = _StubCloud()
    out = asyncio.run(
        engine._answer_cloud("Ciao", api_key="sk-test", base_url="https://x/v1")
    )
    assert out == "ok"
    assert "sent" in captured
    _reset_settings()


def test_anthropic_detection():
    from app.cloud_client import _is_anthropic

    # Detected by key prefix even with default OpenAI endpoint.
    assert _is_anthropic("https://api.openai.com/v1", "sk-ant-abc")
    # Detected by host.
    assert _is_anthropic("https://api.anthropic.com", "whatever")
    # Plain OpenAI key/endpoint is not Anthropic.
    assert not _is_anthropic("https://api.openai.com/v1", "sk-proj-123")
