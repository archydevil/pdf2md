"""whisper.cpp speech-to-text bridge.

Mirrors Meetily's default STT (whisper.cpp, model ggml-large-v3). The flow is:
audio -> ffmpeg decode to 16kHz mono WAV -> whisper.cpp -> segments with
timestamps. Fully offline. Enabled in Fase 5 once the binaries are present.

Configuration via env (KB_ prefix is added by Settings):
  KB_WHISPER_BIN   path to the whisper.cpp `main`/`whisper-cli` binary
  KB_WHISPER_MODEL path to ggml-large-v3.bin
  KB_FFMPEG_BIN    path to ffmpeg (default: "ffmpeg" on PATH)
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


def is_available(whisper_bin: str = "whisper-cli", ffmpeg_bin: str = "ffmpeg") -> bool:
    return bool(_which(whisper_bin)) and bool(_which(ffmpeg_bin))


def _decode_to_wav(audio_path: Path, ffmpeg_bin: str, out_wav: Path) -> None:
    subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(audio_path), "-ar", "16000", "-ac", "1", str(out_wav)],
        check=True,
        capture_output=True,
    )


def transcribe(
    audio_path: str | Path,
    whisper_bin: str = "whisper-cli",
    model_path: str = "ggml-large-v3.bin",
    ffmpeg_bin: str = "ffmpeg",
    language: str = "auto",
) -> list[STTSegment]:
    """Transcribe an audio/video file into timestamped segments.

    Raises RuntimeError if the required binaries/model are missing so callers
    can surface a clear, actionable message.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    wbin = _which(whisper_bin)
    fbin = _which(ffmpeg_bin)
    if not wbin or not fbin or not Path(model_path).exists():
        raise RuntimeError(
            "STT non disponibile. Servono: ffmpeg, binario whisper.cpp "
            f"({whisper_bin}) e modello {model_path}."
        )

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        _decode_to_wav(audio_path, fbin, wav)
        out_prefix = Path(tmp) / "out"
        subprocess.run(
            [
                wbin,
                "-m", model_path,
                "-f", str(wav),
                "-l", language,
                "-oj",  # JSON output
                "-of", str(out_prefix),
            ],
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
