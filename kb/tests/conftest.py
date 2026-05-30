"""Pytest configuration for the KB Forge sidecar test-suite.

Tests here are pure unit tests: no Ollama, no network, no LanceDB writes unless
explicitly using a temp dir. They guard the logic we cannot easily eyeball.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure ``app`` is importable when pytest is run from anywhere.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
