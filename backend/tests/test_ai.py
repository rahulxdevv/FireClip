from __future__ import annotations

import pytest

from app.services import ai, highlights
from app.services.transcription import SegmentData


def _segments() -> list[SegmentData]:
    lines = [
        "Here is the one thing nobody tells you about growing an audience.",
        "I tested this for ninety days and the results surprised me.",
        "The biggest mistake is explaining before you earn attention.",
        "Ask yourself: would you stop scrolling for this first line?",
        "That question changed how I edit every clip.",
        "We measured retention and the difference was almost double.",
        "So the lesson is simple: cut the boring part first.",
        "Then add context only after the hook lands.",
    ]
    segments = []
    for index, line in enumerate(lines):
        start = index * 5000
        segments.append(
            SegmentData(
                start_ms=start,
                end_ms=start + 4800,
                text=line,
                words=[{"word": w, "start_ms": start, "end_ms": start + 400, "confidence": 0.9} for w in line.split()],
            )
        )
    return segments


def test_heuristic_analysis_is_explainable_and_non_overlapping():
    result = highlights.heuristic_analyze(_segments(), target_duration_ms=12000, clip_count=3)
    assert result.provider == "heuristic"
    assert 1 <= len(result.clips) <= 3
    for clip in result.clips:
        assert clip.end_ms > clip.start_ms
        assert clip.explanation
        assert clip.virality_score >= 0
        assert "hook" in clip.signals
        assert "boundaries" in clip.signals
        assert "loudness" in clip.explanation.lower()
    ordered = sorted(result.clips, key=lambda c: c.start_ms)
    for left, right in zip(ordered, ordered[1:]):
        assert right.start_ms >= left.end_ms, "clips must not overlap"


def test_heuristic_never_scores_silence():
    with pytest.raises(ValueError):
        highlights.heuristic_analyze([], target_duration_ms=10000, clip_count=3)


def test_extract_json_handles_fences_and_preamble():
    assert ai.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert ai.extract_json('Sure! Here you go: {"clips": []}') == {"clips": []}
    with pytest.raises(ai.AIError):
        ai.extract_json("no json here")


def test_auto_provider_without_keys_uses_heuristic():
    """No provider credentials are configured in tests, so auto resolves to None."""
    from app.database import SessionLocal

    with SessionLocal() as db:
        assert ai.build_provider(db, None, "auto") is None
        assert ai.build_provider(db, None, "heuristic") is None
        with pytest.raises(ai.AIError):
            ai.build_provider(db, None, "openai")


class _FakeProvider:
    name = "openai"
    model = "test-model"

    def complete(self, system, user, *, json_mode=False, max_tokens=2000):
        return """{"summary": "A test", "topics": ["focus"], "clips": [
        {"start_s": 1, "end_s": 12, "title": "A tight moment", "hook": "Listen",
         "description": "desc", "explanation": "strong hook", "virality_score": 81,
         "engagement_potential": 72, "signals": {"hook": 88, "payoff": 61}}]}"""


def test_llm_analysis_validates_against_transcript():
    result = highlights.llm_analyze(_FakeProvider(), _segments(), target_duration_ms=12000, clip_count=2)
    assert result.provider == "openai"
    assert len(result.clips) == 1
    clip = result.clips[0]
    assert clip.start_ms == 1000
    assert clip.end_ms == 12000
    assert clip.signals["hook"] == 88
    assert clip.transcript_text


class _BadProvider(_FakeProvider):
    def complete(self, *args, **kwargs):
        return "not json"


def test_llm_bad_output_raises_instead_of_faking():
    with pytest.raises(ai.AIError):
        highlights.llm_analyze(_BadProvider(), _segments(), target_duration_ms=12000, clip_count=2)


def test_provider_adapter_parses_openai_response(monkeypatch):
    class Response:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "OK"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"].startswith("Bearer ")
        assert json["messages"][0]["role"] == "system"
        return Response()

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    info = ai.ProviderInfo("openai", "OpenAI", "gpt-test", "https://api.openai.com/v1", "sk-test")
    provider = ai.OpenAIProvider(info)
    assert provider.complete("system", "user") == "OK"


def test_provider_adapter_surfaces_api_errors(monkeypatch):
    class Response:
        status_code = 401
        text = "invalid key"

        def json(self):
            return {}

    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: Response())
    info = ai.ProviderInfo("openai", "OpenAI", "gpt-test", "https://api.openai.com/v1", "sk-test")
    with pytest.raises(ai.AIError):
        ai.OpenAIProvider(info).complete("system", "user")
