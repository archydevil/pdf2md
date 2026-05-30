"""Central configuration for the KB Forge sidecar.

All settings are environment-driven (prefix ``KB_``) so the same code runs
air-gapped by default and only reaches the network when you explicitly enable
the cloud egress in :mod:`app.privacy`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KB_", env_file=".env", extra="ignore")

    # --- Storage -----------------------------------------------------------
    data_dir: Path = Field(default=Path("./.kbdata"), description="Root for all KB data")
    lancedb_dir: Path = Field(default=Path("./.kbdata/lancedb"))

    # --- Ollama (local models) --------------------------------------------
    ollama_host: str = Field(default="http://localhost:11434")
    embed_model: str = Field(default="bge-m3")
    llm_model: str = Field(default="llama3.1:8b")
    # Larger model for heavier local enrichment/classification when available.
    llm_model_heavy: str = Field(default="qwen2.5:32b")

    # --- Retrieval ---------------------------------------------------------
    embed_dim: int = Field(default=1024, description="bge-m3 dense dimension")
    top_k: int = Field(default=8)
    rerank_enabled: bool = Field(default=False)

    # --- STT (Fase 5) ------------------------------------------------------
    whisper_bin: str = Field(default="whisper-cli")
    whisper_model: str = Field(default="ggml-large-v3.bin")
    ffmpeg_bin: str = Field(default="ffmpeg")
    faster_whisper_model: str = Field(default="base", description="faster-whisper size/path")
    stt_language: str = Field(default="auto")

    # --- Privacy / egress --------------------------------------------------
    # Hard air-gap switch. When False, the egress gateway refuses every
    # outbound cloud call regardless of per-request flags.
    allow_cloud_egress: bool = Field(default=False)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lancedb_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
