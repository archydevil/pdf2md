"""Template-driven analysis engine — a faithful local re-implementation of the
Meetily summarization approach.

A template is a JSON file with sections ``{title, instruction, format,
item_format}``. We render the sections into a single instruction, ask the local
LLM to fill them from a transcript/document, and return structured Markdown with
segment references and timestamps (when available).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.ollama_client import OllamaClient

TEMPLATES_DIR = Path(__file__).parent / "templates"


def list_templates() -> list[dict]:
    out = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append({"id": path.stem, "name": data.get("name"), "description": data.get("description")})
        except Exception:
            continue
    return out


def load_template(template_id: str) -> dict:
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template '{template_id}' non trovato in {TEMPLATES_DIR}")
    return json.loads(path.read_text(encoding="utf-8"))


def _render_instructions(template: dict) -> str:
    lines: list[str] = []
    for i, section in enumerate(template.get("sections", []), start=1):
        title = section.get("title", f"Section {i}")
        instruction = section.get("instruction", "")
        fmt = section.get("format", "paragraph")
        item_format = section.get("item_format")
        block = f"### {title}\n- Istruzione: {instruction}\n- Formato: {fmt}"
        if item_format:
            block += f"\n- Schema riga:\n{item_format}"
        lines.append(block)
    return "\n\n".join(lines)


_SYSTEM = (
    "Sei un analista che produce note strutturate in Markdown a partire da una "
    "trascrizione o documento. Compila OGNI sezione richiesta seguendo "
    "istruzione e formato. Quando disponibili, cita il segmento di trascrizione "
    "e il timestamp. Non inventare: se un'informazione manca, scrivi 'n/d'."
)


class AnalysisEngine:
    def __init__(self, ollama: OllamaClient | None = None) -> None:
        self.ollama = ollama or OllamaClient()

    async def analyze(self, content: str, template_id: str, model: str | None = None) -> str:
        template = load_template(template_id)
        instructions = _render_instructions(template)
        prompt = (
            f"# Template: {template.get('name')}\n"
            f"{template.get('description', '')}\n\n"
            f"## Sezioni da compilare\n{instructions}\n\n"
            f"## Contenuto\n\"\"\"\n{content[:16000]}\n\"\"\"\n\n"
            "Produci ora le note in Markdown, una sezione per ciascun titolo."
        )
        return await self.ollama.generate(prompt, system=_SYSTEM, temperature=0.1, model=model)
