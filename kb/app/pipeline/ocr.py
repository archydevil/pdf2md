"""OCR for scanned documents and images.

Offline-first: tries RapidOCR (ONNX, fully local, multilingual) and falls back
to the local vision model in Ollama (llama3.2-vision) when RapidOCR isn't
installed. Both keep the air-gap guarantee — nothing leaves the machine.
"""
from __future__ import annotations

import base64
from pathlib import Path

from app.config import get_settings


def is_available() -> bool:
    try:
        import rapidocr_onnxruntime  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


def _ocr_rapid(path: Path) -> str | None:
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
    except Exception:
        return None
    engine = RapidOCR()
    result, _ = engine(str(path))
    if not result:
        return ""
    # result rows: [box, text, score]
    return "\n".join(row[1] for row in result)


async def _ocr_vision(path: Path, model: str = "llama3.2-vision") -> str | None:
    """Fallback OCR via a local vision LLM in Ollama."""
    import httpx

    host = get_settings().ollama_host.rstrip("/")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "prompt": (
            "Estrai TUTTO il testo visibile in questa immagine, preservando "
            "l'ordine di lettura. Restituisci solo il testo, senza commenti."
        ),
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0.0},
    }
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(f"{host}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
    except Exception:
        return None


async def ocr_image(path: str | Path, vision_model: str = "llama3.2-vision") -> str:
    """Return extracted text from an image, raising if no OCR backend works."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    text = _ocr_rapid(path)
    if text is not None:
        return text

    text = await _ocr_vision(path, model=vision_model)
    if text is not None:
        return text

    raise RuntimeError(
        "OCR non disponibile. Installa RapidOCR (pip install rapidocr-onnxruntime) "
        "oppure assicurati che il modello vision sia presente in Ollama "
        f"({vision_model})."
    )
