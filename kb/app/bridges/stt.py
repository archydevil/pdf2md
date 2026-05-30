"""Speech-to-text bridge (Fase 5).

Two interchangeable backends, both fully offline:

  * ``whisper.cpp`` — mirrors Meetily's default (ggml-large-v3). Preferred when
    the binary + model are present. Flow: audio -> ffmpeg 16kHz mono WAV ->
    whisper.cpp -> JSON segments with timestamps.
  * ``faster-whisper`` — pure-wheel CTranslate2 runtime (same Whisper weights).
    No external ffmpeg or compiler needed; the model is downloaded once and then
    runs offline. Used as automatic fallback so STT works out-of-the-box.

Configuration via env (Settings adds the ``KB_`` prefix):
  KB_WHISPER_BIN         path to whisper.cpp `whisper-cli`/`main`
  KB_WHISPER_MODEL       path to ggml-large-v3.bin
  KB_FFMPEG_BIN          path to ffmpeg (default: "ffmpeg" on PATH)
  KB_FASTER_WHISPER_MODEL faster-whisper model size/path (default: "base")
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class STTSegment:
    text: str
    t_start: float
    t_end: float


def _which(candidate: str) -> str | None:
    if Path(candidate).exists():
        return candidate
    return shutil.which(candidate)


def whispercpp_available(whisper_bin: str = "whisper-cli", ffmpeg_bin: str = "ffmpeg") -> bool:
    return bool(_which(whisper_bin)) and bool(_which(ffmpeg_bin))


def faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401  # type: ignore[import-not-found]
    except Exception:
        return False
    return True


def is_available(whisper_bin: str = "whisper-cli", ffmpeg_bin: str = "ffmpeg") -> bool:
    """True when *any* backend can run."""
    return whispercpp_available(whisper_bin, ffmpeg_bin) or faster_whisper_available()


# --------------------------------------------------------------------------- #
# Backend: whisper.cpp                                                         #
# --------------------------------------------------------------------------- #
def _decode_to_wav(audio_path: Path, ffmpeg_bin: str, out_wav: Path) -> None:
    subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(audio_path), "-ar", "16000", "-ac", "1", str(out_wav)],
        check=True,
        capture_output=True,
    )


def transcribe_whispercpp(
    audio_path: Path,
    whisper_bin: str,
    model_path: str,
    ffmpeg_bin: str,
    language: str,
) -> list[STTSegment]:
    wbin = _which(whisper_bin)
    fbin = _which(ffmpeg_bin)
    if not wbin or not fbin or not Path(model_path).exists():
        raise RuntimeError(
            "whisper.cpp non disponibile. Servono ffmpeg, binario "
            f"({whisper_bin}) e modello {model_path}."
        )
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        _decode_to_wav(audio_path, fbin, wav)
        out_prefix = Path(tmp) / "out"
        subprocess.run(
            [wbin, "-m", model_path, "-f", str(wav), "-l", language, "-oj", "-of", str(out_prefix)],
            check=True,
            capture_output=True,
        )
        data = json.loads((out_prefix.with_suffix(".json")).read_text(encoding="utf-8"))
    segments: list[STTSegment] = []
    for seg in data.get("transcription", []):
        offsets = seg.get("offsets", {})
        segments.append(
            STTSegment(
                text=seg.get("text", "").strip(),
                t_start=offsets.get("from", 0) / 1000.0,
                t_end=offsets.get("to", 0) / 1000.0,
            )
        )
    return segments


# --------------------------------------------------------------------------- #
# Backend: faster-whisper                                                      #
# --------------------------------------------------------------------------- #
_FASTER_CACHE: dict[str, object] = {}


def _load_faster(model_size: str):  # noqa: ANN202 - optional dependency type
    from faster_whisper import WhisperModel  # type: ignore[import-not-found]

    if model_size not in _FASTER_CACHE:
        # int8 on CPU keeps it light and fully local.
        _FASTER_CACHE[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _FASTER_CACHE[model_size]


def transcribe_faster(
    audio_path: Path,
    model_size: str = "base",
    language: str | None = None,
) -> list[STTSegment]:
    model = _load_faster(model_size)
    lang = None if language in (None, "auto") else language
    segments, _info = model.transcribe(str(audio_path), language=lang, vad_filter=True)
    return [STTSegment(text=s.text.strip(), t_start=s.start, t_end=s.end) for s in segments]


# --------------------------------------------------------------------------- #
# Unified entry                                                               #
# --------------------------------------------------------------------------- #
def transcribe(
    audio_path: str | Path,
    whisper_bin: str = "whisper-cli",
    model_path: str = "ggml-large-v3.bin",
    ffmpeg_bin: str = "ffmpeg",
    language: str = "auto",
    faster_model: str = "base",
) -> list[STTSegment]:
    """Transcribe audio/video into timestamped segments.

    Prefers whisper.cpp (Meetily parity); falls back to faster-whisper. Raises
    RuntimeError with an actionable message when no backend is usable.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    if whispercpp_available(whisper_bin, ffmpeg_bin) and Path(model_path).exists():
        return transcribe_whispercpp(audio_path, whisper_bin, model_path, ffmpeg_bin, language)

    if faster_whisper_available():
        return transcribe_faster(audio_path, model_size=faster_model, language=language)

    raise RuntimeError(
        "STT non disponibile. Installa faster-whisper (pip install faster-whisper) "
        f"oppure fornisci whisper.cpp ({whisper_bin}) + ffmpeg + modello {model_path}."
    )


def segments_to_markdown(segments: list[STTSegment], title: str) -> str:
    """Render STT segments as a transcript Markdown with [mm:ss] timestamps."""
    lines = [f"# {title}", ""]
    for seg in segments:
        if not seg.text:
            continue
        mm, ss = divmod(int(seg.t_start), 60)
        lines.append(f"[{mm:02d}:{ss:02d}] {seg.text}")
    return "\n".join(lines) + "\n"
