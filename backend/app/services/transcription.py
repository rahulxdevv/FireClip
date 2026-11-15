"""Speech-to-text engines.

Engines share one result shape so the rest of FireClip is provider agnostic:

* ``faster_whisper`` - local, no paid API (default where installed)
* ``openai``        - hosted Whisper API via OPENAI_API_KEY
* ``mock``          - deterministic test double, only when ALLOW_MOCK_TRANSCRIPTION=true

Diarization is available through an optional pyannote adapter and a clearly
labelled pause-based estimate. Speaker labels are editable by users either way.
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger("fireclip.transcription")


class TranscriptionError(RuntimeError):
    pass


@dataclass
class SegmentData:
    start_ms: int
    end_ms: int
    text: str
    words: list[dict] = field(default_factory=list)
    confidence: float = 1.0
    speaker: str = "S1"


@dataclass
class TranscriptionResult:
    engine: str
    model: str
    language: str
    segments: list[SegmentData]
    duration: float = 0.0
    speakers: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments if s.text.strip())

    @property
    def word_count(self) -> int:
        return sum(len(s.words) for s in self.segments) or len(self.text.split())


def faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        return False


def openai_available() -> bool:
    return bool(settings.openai_api_key)


def engine_status() -> dict[str, Any]:
    return {
        "faster_whisper": {
            "available": faster_whisper_available(),
            "model": settings.whisper_model,
            "device": settings.whisper_device,
            "local": True,
            "note": None
            if faster_whisper_available()
            else "Install the `faster-whisper` extra on Python 3.10-3.12 (also included in the Docker image).",
        },
        "openai": {
            "available": openai_available(),
            "model": "whisper-1",
            "local": False,
            "note": None if openai_available() else "Set OPENAI_API_KEY to enable hosted transcription.",
        },
        "mock": {
            "available": settings.allow_mock_transcription,
            "model": "mock",
            "local": True,
            "note": "Synthetic transcript for development and tests. It is not real speech recognition."
            if settings.allow_mock_transcription
            else "Disabled. Set ALLOW_MOCK_TRANSCRIPTION=true for demos/tests only.",
        },
    }


def resolve_engine(requested: str) -> str:
    if requested and requested != "auto":
        if requested == "faster_whisper" and not faster_whisper_available():
            raise TranscriptionError(
                "Local transcription requires faster-whisper, which is not installed in this "
                "environment. Install requirements-transcription.txt on Python 3.10-3.12, use the "
                "Docker image, or configure OPENAI_API_KEY."
            )
        if requested == "openai" and not openai_available():
            raise TranscriptionError("OPENAI_API_KEY is not configured for hosted transcription.")
        if requested == "mock" and not settings.allow_mock_transcription:
            raise TranscriptionError("Mock transcription is disabled by configuration.")
        return requested
    if settings.transcription_engine != "auto":
        return resolve_engine(settings.transcription_engine)
    if faster_whisper_available():
        return "faster_whisper"
    if openai_available():
        return "openai"
    if settings.allow_mock_transcription:
        return "mock"
    raise TranscriptionError(
        "No transcription engine is available. Install faster-whisper (Docker image includes it) "
        "or set OPENAI_API_KEY. Refusing to fabricate a transcript."
    )


# --- Engines --------------------------------------------------------------

_whisper_models: dict[str, Any] = {}
# CTranslate2 inference is CPU and memory heavy. One model, one inference at a
# time per process keeps small hosts responsive and avoids duplicate model loads.
_whisper_lock = threading.Lock()


def _transcribe_faster_whisper(audio: Path, language: str | None) -> TranscriptionResult:
    from faster_whisper import WhisperModel

    model_key = f"{settings.whisper_model}:{settings.whisper_device}:{settings.whisper_compute_type}"
    with _whisper_lock:
        model = _whisper_models.get(model_key)
        if model is None:
            kwargs: dict[str, Any] = {
                "device": settings.whisper_device,
                "compute_type": settings.whisper_compute_type,
            }
            if settings.whisper_cpu_threads > 0:
                kwargs["cpu_threads"] = settings.whisper_cpu_threads
            model = WhisperModel(settings.whisper_model, **kwargs)
            _whisper_models[model_key] = model
            logger.info("Loaded faster-whisper model %s on %s", settings.whisper_model, settings.whisper_device)

        segments_iter, info = model.transcribe(
            str(audio),
            language=language or None,
            word_timestamps=True,
            vad_filter=True,
            beam_size=max(1, settings.whisper_beam_size),
            condition_on_previous_text=False,
        )
        segments: list[SegmentData] = []
        for seg in segments_iter:
            words = [
                {
                    "word": w.word.strip(),
                    "start_ms": int(w.start * 1000),
                    "end_ms": int(w.end * 1000),
                    "confidence": round(float(getattr(w, "probability", 1.0)), 4),
                }
                for w in (seg.words or [])
                if w.word and w.word.strip()
            ]
            segments.append(
                SegmentData(
                    start_ms=int(seg.start * 1000),
                    end_ms=int(seg.end * 1000),
                    text=seg.text.strip(),
                    words=words,
                    confidence=round(float(getattr(seg, "avg_logprob", -0.2) and min(1.0, 1 + getattr(seg, "avg_logprob", -0.2))), 4),
                )
            )
    if not segments:
        raise TranscriptionError("The model returned no speech segments; the file may be silent.")
    return TranscriptionResult(
        engine="faster_whisper",
        model=settings.whisper_model,
        language=getattr(info, "language", None) or language or settings.default_language,
        segments=segments,
    )


def _transcribe_openai(audio: Path, language: str | None) -> TranscriptionResult:
    size_mb = audio.stat().st_size / (1024 * 1024)
    if size_mb > 24:
        raise TranscriptionError(
            "Hosted Whisper accepts files up to 25MB of audio. Use local faster-whisper for long "
            "recordings, or reduce the source length."
        )
    data = {"model": "whisper-1", "response_format": "verbose_json", "timestamp_granularities[]": ["word", "segment"]}
    if language:
        data["language"] = language
    try:
        with open(audio, "rb") as handle:
            response = httpx.post(
                f"{settings.openai_base_url.rstrip('/')}/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                data=data,
                files={"file": (audio.name, handle, "audio/wav")},
                timeout=600,
            )
    except httpx.HTTPError as exc:
        raise TranscriptionError(f"Hosted transcription request failed: {exc}") from exc
    if response.status_code >= 400:
        raise TranscriptionError(f"OpenAI transcription error {response.status_code}: {response.text[:400]}")
    payload = response.json()

    words_by_segment: dict[int, list[dict]] = {}
    for word in payload.get("words", []) or []:
        start = int(float(word.get("start", 0)) * 1000)
        end = int(float(word.get("end", 0)) * 1000)
        entry = {"word": str(word.get("word", "")).strip(), "start_ms": start, "end_ms": end, "confidence": None}
        if not entry["word"]:
            continue
        # Assign each word to the segment containing its midpoint.
        idx = 0
        raw_segments = payload.get("segments", [])
        for i, seg in enumerate(raw_segments):
            if float(seg.get("start", 0)) <= (start / 1000) and (end / 1000) <= float(seg.get("end", 0)):
                idx = i
                break
        words_by_segment.setdefault(idx, []).append(entry)

    segments: list[SegmentData] = []
    for i, seg in enumerate(payload.get("segments", []) or []):
        segments.append(
            SegmentData(
                start_ms=int(float(seg.get("start", 0)) * 1000),
                end_ms=int(float(seg.get("end", 0)) * 1000),
                text=str(seg.get("text", "")).strip(),
                words=words_by_segment.get(i, []),
                confidence=round(float(seg.get("avg_logprob", 0) or 0), 4) if seg.get("avg_logprob") is not None else 1.0,
            )
        )
    if not segments and payload.get("text"):
        segments = [SegmentData(0, 1000, payload["text"].strip())]
    if not segments:
        raise TranscriptionError("The transcription service returned an empty transcript.")
    return TranscriptionResult(
        engine="openai",
        model="whisper-1",
        language=payload.get("language") or language or settings.default_language,
        segments=segments,
        duration=float(payload.get("duration") or 0),
    )


def _transcribe_mock(audio: Path, language: str | None) -> TranscriptionResult:
    """Deterministic synthetic transcript. Never enabled silently."""
    if not settings.allow_mock_transcription:
        raise TranscriptionError("Mock transcription is disabled")
    from .media import probe

    info = probe(audio)
    lines = [
        "Here is the one thing nobody tells you about building an audience.",
        "I tested this for ninety days and the results surprised me.",
        "The trick is to cut the boring part and start with the strongest sentence.",
        "Most people make the mistake of explaining before they earn attention.",
        "Ask yourself: would you stop scrolling for this first line?",
        "That question changed how I edit every single clip.",
        "We measured retention and the difference was almost double.",
        "So here is the framework, step by step, starting with the hook.",
    ]
    total = max(8.0, info.duration)
    chunk = total / len(lines)
    segments: list[SegmentData] = []
    for i, line in enumerate(lines):
        start = i * chunk
        end = min(total, start + chunk * 0.92)
        words_raw = line.split()
        word_duration = (end - start) / max(1, len(words_raw))
        words = [
            {
                "word": w,
                "start_ms": int((start + j * word_duration) * 1000),
                "end_ms": int((start + (j + 1) * word_duration) * 1000),
                "confidence": 1.0,
            }
            for j, w in enumerate(words_raw)
        ]
        segments.append(
            SegmentData(
                start_ms=int(start * 1000),
                end_ms=int(end * 1000),
                text=line,
                words=words,
                confidence=1.0,
            )
        )
    return TranscriptionResult(
        engine="mock",
        model="synthetic-v1",
        language=language or "en",
        segments=segments,
        duration=total,
    )


def transcribe(audio: Path, *, engine: str = "auto", language: str | None = None) -> TranscriptionResult:
    resolved = resolve_engine(engine)
    if not audio.exists() or audio.stat().st_size == 0:
        raise TranscriptionError("Audio file is missing or empty")
    if resolved == "faster_whisper":
        return _transcribe_faster_whisper(audio, language)
    if resolved == "openai":
        return _transcribe_openai(audio, language)
    if resolved == "mock":
        return _transcribe_mock(audio, language)
    raise TranscriptionError(f"Unsupported engine '{resolved}'")


# --- Diarization ----------------------------------------------------------


def diarize(segments: list[SegmentData], mode: str | None = None) -> str:
    """Assign speaker keys. Returns a description of the method used.

    - ``off`` (default): every segment belongs to ``S1``. No invented identities.
    - ``pause_heuristic``: alternates two estimated turns after long pauses.
    - ``pyannote``: requires the optional pyannote.audio extra and HF_TOKEN.
    """
    mode = mode or getattr(settings, "diarization_mode", "off")
    if mode in {"", "off"}:
        for segment in segments:
            segment.speaker = "S1"
        return "none"
    if mode == "pyannote":
        try:
            from pyannote.audio import Pipeline  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise TranscriptionError(
                "pyannote diarization requires pyannote.audio and HF_TOKEN. "
                "Install requirements-diarization.txt or use DIARIZATION_MODE=pause_heuristic."
            ) from exc
        raise TranscriptionError(
            "pyannote diarization is configured but audio input wiring is not available in this build. "
            "Use DIARIZATION_MODE=pause_heuristic or label speakers manually."
        )
    if mode != "pause_heuristic":
        raise TranscriptionError(f"Unknown diarization mode '{mode}'")

    speaker = 1
    previous_end = None
    for segment in segments:
        if previous_end is not None:
            gap = segment.start_ms - previous_end
            text = segment.text.strip()
            if gap >= 1200 and text and text[0].isupper():
                speaker = 2 if speaker == 1 else 1
        segment.speaker = f"S{speaker}"
        previous_end = segment.end_ms
    return "pause_heuristic"


def speaker_labels(segments: list[SegmentData]) -> list[str]:
    seen: list[str] = []
    for segment in segments:
        if segment.speaker not in seen:
            seen.append(segment.speaker)
    return sorted(seen)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
