from __future__ import annotations

import subprocess

import pytest

from app.config import settings
from app.services import transcription
from app.services.transcription import SegmentData


@pytest.fixture(scope="module")
def audio_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("audio") / "tone.wav"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostdin", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
            "-t", "6", "-ac", "1", "-ar", "16000", str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def test_mock_engine_returns_word_timestamps(audio_file):
    result = transcription.transcribe(audio_file, engine="mock")
    assert result.engine == "mock"
    assert result.segments
    assert result.word_count > 20
    assert result.segments[0].words
    assert all("start_ms" in word for word in result.segments[0].words)
    assert result.language == "en"


def test_diarization_modes():
    segments = [
        SegmentData(0, 1000, "First line."),
        SegmentData(2000, 3000, "Second line."),
        SegmentData(6000, 7000, "Third line."),
    ]
    assert transcription.diarize(segments, "off") == "none"
    assert {s.speaker for s in segments} == {"S1"}

    segments = [
        SegmentData(0, 1000, "First line."),
        SegmentData(4000, 5000, "Second line."),
    ]
    assert transcription.diarize(segments, "pause_heuristic") == "pause_heuristic"
    assert len({s.speaker for s in segments}) == 2


def test_mock_engine_disabled_by_configuration(audio_file, monkeypatch):
    monkeypatch.setattr(settings, "allow_mock_transcription", False)
    with pytest.raises(transcription.TranscriptionError):
        transcription.transcribe(audio_file, engine="mock")


def test_missing_engine_gives_actionable_error(audio_file, monkeypatch):
    monkeypatch.setattr(transcription, "faster_whisper_available", lambda: False)
    monkeypatch.setattr(transcription, "openai_available", lambda: False)
    monkeypatch.setattr(settings, "allow_mock_transcription", False)
    monkeypatch.setattr(settings, "transcription_engine", "auto")
    with pytest.raises(transcription.TranscriptionError) as exc:
        transcription.resolve_engine("auto")
    assert "faster-whisper" in str(exc.value) or "OPENAI_API_KEY" in str(exc.value)


def test_engine_status_reports_availability():
    status = transcription.engine_status()
    assert set(status.keys()) == {"faster_whisper", "openai", "mock"}
    assert status["faster_whisper"]["local"] is True
