"""Clip intelligence.

Two analyzers share one explainable output contract:

1. ``heuristic`` - deterministic multi-signal scoring over the transcript. It
   never uses "loudness equals virality"; every score is decomposed into named
   signals the UI can show.
2. LLM providers - prompted for the same JSON shape and validated locally.

Every candidate carries an explanation, a hook, a transcript excerpt and a
signal breakdown.
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AnalyticsRecord, CandidateClip, PublishingJob
from .ai import AIError, LLMProvider, extract_json
from .transcription import SegmentData

logger = logging.getLogger("fireclip.highlights")

STOPWORDS = set(
    """a an the and or but if then than that this these those of to in on for with as at by from is are was were be been being
    it its it's i you he she we they me him her us them my your our their what which who whom when where why how not no yes
    do does did doing have has had having will would can could should may might must just very really so about into over under
    more most much many some any all out up down there here their they're you're we're i'm don't doesn't isn't aren't""".split()
)

HOOK_PHRASES = (
    "here's", "heres", "the biggest", "the one thing", "nobody tells you", "what nobody",
    "most people", "i tested", "i tried", "the truth", "let me tell you", "imagine",
    "what if", "stop doing", "you need to", "the secret", "the mistake", "listen",
    "this is why", "here is", "did you know", "the problem is", "the reason",
)
CURIOSITY_WORDS = ("why", "how", "what", "secret", "nobody", "truth", "mistake", "wrong", "hidden", "surprising", "actually")
EMOTION_WORDS = {
    "love": 2, "hate": 2, "amazing": 2, "terrible": 2, "crazy": 2, "insane": 2,
    "shocked": 3, "unbelievable": 3, "wild": 2, "honest": 1, "scary": 2, "afraid": 2,
    "excited": 2, "angry": 2, "painful": 2, "hilarious": 3, "funny": 2, "brutal": 2,
    "incredible": 3, "awful": 2, "obsessed": 2, "fascinating": 2, "depressing": 2,
    "embarrassing": 2, "proud": 1, "shocked": 3, "surprised": 2, "fantastic": 2,
}
SPECIFICITY_RE = re.compile(r"(\b\d+(?:\.\d+)?\s?(?:%|percent|x|times|k|m|million|billion|dollars|usd|hours?|days?|weeks?|months?|years?)\b|\$\d[\d,.]*|\b(19|20)\d{2}\b)", re.I)
STORY_MARKERS = ("i was", "we were", "one day", "then i", "and then", "suddenly", "ended up", "growing up", "at first", "after that", "the first time", "i remember")
PAYOFF_MARKERS = ("so the lesson", "that's why", "thats why", "in the end", "which means", "the takeaway", "here's the thing", "the point is", "bottom line", "what i learned")
FILLERS = ("um", "uh", "erm", "you know", "i mean", "basically", "kind of", "sort of", "like,")
LAUGH_MARKERS = ("[laughter]", "(laughs)", "haha", "hahaha")


@dataclass
class ClipCandidate:
    start_ms: int
    end_ms: int
    title: str
    description: str
    hook: str
    transcript_text: str
    explanation: str
    virality_score: float
    engagement_potential: float
    signals: dict[str, float] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    summary: str
    topics: list[str]
    clips: list[ClipCandidate]
    provider: str
    model: str


def _words(segment: SegmentData) -> list[str]:
    return re.findall(r"[A-Za-z0-9'$%]+", segment.text)


def _keywords(text: str) -> list[str]:
    words = [w.lower().strip(".,!?;:\"'()[]") for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text)]
    return [w for w in words if w and w not in STOPWORDS]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _ends_sentence(text: str) -> bool:
    return bool(re.search(r"[.!?…][\"')\]]?$", text.strip()))


def _sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _trim_title(text: str, limit: int = 68) -> str:
    text = re.sub(r"^(and|but|so|then|because|um|uh|you know)[,\s]+", "", text.strip(), flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(' ,-')
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + "…"


def _build_windows(segments: list[SegmentData], target_ms: int) -> Iterable[tuple[int, int]]:
    """Segment-aligned windows whose duration hugs the target length."""
    if not segments:
        return []
    min_ms = max(6000, int(target_ms * 0.55))
    max_ms = int(target_ms * 1.45)
    windows: list[tuple[int, int]] = []
    for i in range(len(segments)):
        total = 0
        for j in range(i, len(segments)):
            total = segments[j].end_ms - segments[i].start_ms
            if total > max_ms:
                break
            if total >= min_ms:
                windows.append((i, j))
    # De-duplicate identical boundaries and cap the search space.
    return list(dict.fromkeys(windows))


def _score_window(
    segments: list[SegmentData],
    start_idx: int,
    end_idx: int,
    doc_freq: dict[str, int],
    transcript_words: int,
) -> tuple[float, float, dict[str, float]]:
    window = segments[start_idx : end_idx + 1]
    text = " ".join(s.text for s in window).strip()
    if not text:
        return 0.0, 0.0, {}
    words = _keywords(text)
    duration_s = max(1.0, (window[-1].end_ms - window[0].start_ms) / 1000)
    sentences = _sentence_split(text)
    first_words = " ".join(w.text for w in window[:2]).lower()
    lower = text.lower()

    hook_hits = sum(1 for phrase in HOOK_PHRASES if phrase in first_words)
    hook = _clamp(hook_hits * 0.45 + (0.25 if "?" in " ".join(sentences[:1]) else 0))
    curiosity = _clamp(
        sum(1 for w in CURIOSITY_WORDS if w in lower) / 10
        + lower.count("?") * 0.12
        + sum(1 for w in ("you", "your") if w in words) * 0.06
    )
    emotion_points = sum(weight for word, weight in EMOTION_WORDS.items() if word in lower)
    emotion = _clamp(emotion_points / 10)
    specifics = len(SPECIFICITY_RE.findall(text))
    specificity = _clamp(specifics / 5)
    story = _clamp(sum(1 for marker in STORY_MARKERS if marker in lower) / 4)
    payoff = _clamp(sum(1 for marker in PAYOFF_MARKERS if marker in lower) / 3)
    laughter = 1.0 if any(marker in lower for marker in LAUGH_MARKERS) else 0.0

    filler_hits = sum(lower.count(filler) for filler in FILLERS)
    clarity = _clamp(1 - filler_hits / max(6, len(words) * 0.12))
    wps = len(text.split()) / duration_s
    density = _clamp(1 - abs(wps - 3.0) / 3.0)

    previous_ok = start_idx == 0 or _ends_sentence(segments[start_idx - 1].text)
    boundary = (0.6 if previous_ok else 0.1) + (0.4 if _ends_sentence(window[-1].text) else 0.0)
    boundary = _clamp(boundary)

    speakers = len({s.speaker for s in window})
    dynamics = _clamp(0.45 + (speakers - 1) * 0.3) if speakers > 1 else 0.35

    # Topical focus: how concentrated are the window's keywords vs the document.
    if words:
        unique = set(words)
        focus = sum((doc_freq.get(w, 1) / max(1, transcript_words)) * 4 for w in unique) / len(unique)
    else:
        focus = 0.0
    focus = _clamp(focus)

    signals = {
        "hook": round(hook * 100, 1),
        "curiosity": round(curiosity * 100, 1),
        "emotion": round(emotion * 100, 1),
        "specificity": round(specificity * 100, 1),
        "storytelling": round(story * 100, 1),
        "payoff": round(payoff * 100, 1),
        "clarity": round(clarity * 100, 1),
        "speech_density": round(density * 100, 1),
        "boundaries": round(boundary * 100, 1),
        "dialogue": round(dynamics * 100, 1),
        "topical_focus": round(focus * 100, 1),
        "humor": round(laughter * 100, 1),
    }
    weights = {
        "hook": 0.20,
        "curiosity": 0.11,
        "emotion": 0.10,
        "specificity": 0.08,
        "storytelling": 0.08,
        "payoff": 0.09,
        "clarity": 0.08,
        "speech_density": 0.05,
        "boundaries": 0.08,
        "dialogue": 0.05,
        "topical_focus": 0.05,
        "humor": 0.03,
    }
    raw = sum(signals[key] / 100 * weight for key, weight in weights.items())
    score = _clamp(raw * 1.18) * 100
    engagement = _clamp(
        (signals["hook"] * 0.3 + signals["curiosity"] * 0.25 + signals["emotion"] * 0.2 + signals["payoff"] * 0.15 + signals["dialogue"] * 0.1) / 100
    ) * 100
    return round(score, 1), round(engagement, 1), signals


def _explain(signals: dict[str, float], duration_s: float, speakers: int) -> str:
    labels = {
        "hook": "a strong opening hook",
        "curiosity": "an open curiosity gap",
        "emotion": "emotionally charged language",
        "specificity": "concrete numbers or facts",
        "storytelling": "narrative momentum",
        "payoff": "a clear payoff line",
        "clarity": "clean, low-filler delivery",
        "speech_density": "a comfortable speaking pace",
        "boundaries": "clean start and end boundaries",
        "dialogue": "back-and-forth dialogue",
        "topical_focus": "a tight, focused topic",
        "humor": "a moment of humor",
    }
    ranked = sorted(signals.items(), key=lambda item: item[1], reverse=True)
    top = [labels[key] for key, value in ranked[:3] if value >= 55]
    if not top:
        top = [labels[ranked[0][0]]] if ranked else ["the strongest available moment"]
    weaknesses = [labels[key] for key, value in ranked[-2:] if value < 35]
    reasons = ", ".join(top[:-1]) + (" and " if len(top) > 1 else "") + top[-1]
    text = f"Chosen for {reasons}. It runs {duration_s:.0f}s and opens on a sentence boundary so it works as a standalone clip."
    if speakers > 1:
        text += " The window contains a speaker exchange, which adds conversational energy."
    if weaknesses:
        text += f" Weak spots to review: {', '.join(weaknesses)}."
    text += " Scores come from transcript signals only - never from audio loudness."
    return text


def _title_for(window: list[SegmentData]) -> str:
    text = " ".join(s.text for s in window[:3]).strip()
    sentences = _sentence_split(text)
    if not sentences:
        return "Untitled moment"
    # Prefer the first sentence that is not a pure filler fragment.
    best = sentences[0]
    for sentence in sentences[:3]:
        if 18 <= len(sentence) <= 110:
            best = sentence
            break
    return _trim_title(best)


def heuristic_analyze(
    segments: list[SegmentData],
    *,
    target_duration_ms: int = 45000,
    clip_count: int = 6,
    total_duration_ms: int | None = None,
) -> AnalysisResult:
    if not segments:
        raise ValueError("Cannot analyze an empty transcript")
    transcript_text = " ".join(s.text for s in segments)
    keywords = _keywords(transcript_text)
    doc_freq: dict[str, int] = {}
    for word in keywords:
        doc_freq[word] = doc_freq.get(word, 0) + 1
    windows = _build_windows(segments, target_duration_ms)
    if not windows:
        start = segments[0].start_ms
        end = segments[-1].end_ms
        windows = [(0, len(segments) - 1)]
    scored = []
    for start_idx, end_idx in windows:
        score, engagement, signals = _score_window(segments, start_idx, end_idx, doc_freq, len(keywords))
        if score <= 0:
            continue
        scored.append((score, engagement, signals, start_idx, end_idx))
    scored.sort(key=lambda item: item[0], reverse=True)

    selected: list[tuple[float, float, dict[str, float], int, int]] = []
    for candidate in scored:
        _score, _engagement, _signals, start_idx, end_idx = candidate
        start_ms, end_ms = segments[start_idx].start_ms, segments[end_idx].end_ms
        overlap = False
        for chosen in selected:
            c_start = segments[chosen[3]].start_ms
            c_end = segments[chosen[4]].end_ms
            shared = max(0, min(end_ms, c_end) - max(start_ms, c_start))
            if shared > 0.25 * min(end_ms - start_ms, c_end - c_start):
                overlap = True
                break
        if not overlap:
            selected.append(candidate)
        if len(selected) >= clip_count:
            break

    clips: list[ClipCandidate] = []
    for score, engagement, signals, start_idx, end_idx in selected:
        window = segments[start_idx : end_idx + 1]
        start_ms, end_ms = window[0].start_ms, window[-1].end_ms
        text = " ".join(s.text for s in window).strip()
        sentences = _sentence_split(text)
        hook = _trim_title(sentences[0], 160) if sentences else _trim_title(text, 160)
        speakers = len({s.speaker for s in window})
        clips.append(
            ClipCandidate(
                start_ms=start_ms,
                end_ms=end_ms,
                title=_title_for(window),
                description=_trim_title(text, 280),
                hook=hook,
                transcript_text=text,
                explanation=_explain(signals, (end_ms - start_ms) / 1000, speakers),
                virality_score=score,
                engagement_potential=engagement,
                signals=signals,
            )
        )

    topic_counts: dict[str, int] = {}
    for word in keywords:
        topic_counts[word] = topic_counts.get(word, 0) + 1
    topics = [word for word, _count in sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]]
    summary = _summary(transcript_text, topics, total_duration_ms)
    return AnalysisResult(
        summary=summary,
        topics=topics,
        clips=clips,
        provider="heuristic",
        model="fireclip-signals-v1",
    )


def _summary(transcript_text: str, topics: list[str], total_duration_ms: int | None) -> str:
    sentences = _sentence_split(transcript_text)
    lead = sentences[0][:220] if sentences else transcript_text[:220]
    duration_note = f" across {total_duration_ms / 60000:.0f} minutes" if total_duration_ms else ""
    topic_note = f" Recurring themes: {', '.join(topics[:5])}." if topics else ""
    return f"{lead}{duration_note}.{topic_note}"


LLM_SYSTEM = """You are FireClip's senior short-form video editor. You find standalone moments in
long transcripts that would perform on TikTok, Reels and Shorts. Judge content by context,
story, emotion, curiosity and payoff. Never equate loudness with virality. Return only JSON."""

LLM_TEMPLATE = """Analyse this transcript and select {count} non-overlapping clips of roughly
{seconds} seconds each.

Requirements:
- Start exactly at a spoken sentence boundary. Use transcript timestamps in seconds.
- Each clip must make sense without outside context.
- Titles: specific, curiosity-driven, max 70 characters, no clickbait lies.
- Hooks: the actual opening line or a faithful one-sentence hook.
- Explanations: cite which signals drove the score.
- virality_score and engagement_potential: 0-100 integers.
- Signals object with 0-100 values for: hook, curiosity, emotion, specificity, storytelling,
  payoff, clarity, boundaries, dialogue, topical_focus, humor.

Return JSON exactly in this shape:
{{"summary": "...", "topics": ["..."], "clips": [
  {{"start_s": 12.5, "end_s": 51.2, "title": "...", "hook": "...", "description": "...",
    "explanation": "...", "virality_score": 82, "engagement_potential": 76,
    "signals": {{"hook": 80, "curiosity": 70, "emotion": 60, "specificity": 40,
      "storytelling": 55, "payoff": 65, "clarity": 90, "boundaries": 85,
      "dialogue": 50, "topical_focus": 75, "humor": 10}}}}]}}

{performance_context}

TRANSCRIPT (timestamps in seconds):
{transcript}"""


def transcript_for_prompt(segments: list[SegmentData], max_chars: int = 48000) -> str:
    lines = []
    used = 0
    for seg in segments:
        line = f"[{seg.start_ms / 1000:.1f}-{seg.end_ms / 1000:.1f}] {seg.speaker}: {seg.text.strip()}"
        if used + len(line) > max_chars:
            lines.append("...(transcript truncated for length)...")
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines)


def performance_context(db: Session, workspace_id: str) -> str:
    """Real historical performance used to bias future recommendations."""
    rows = db.execute(
        select(PublishingJob.title, AnalyticsRecord.views, AnalyticsRecord.likes, AnalyticsRecord.retention_pct)
        .join(AnalyticsRecord, AnalyticsRecord.publishing_job_id == PublishingJob.id)
        .where(PublishingJob.workspace_id == workspace_id, AnalyticsRecord.views > 0)
        .order_by(AnalyticsRecord.views.desc())
        .limit(8)
    ).all()
    if not rows:
        return "HISTORICAL PERFORMANCE: none yet. Do not invent metrics; rely on editorial judgement."
    lines = [
        f"- \"{row.title[:80]}\": {row.views} views, {row.likes} likes, {row.retention_pct:.0f}% retention"
        for row in rows
    ]
    return "HISTORICAL PERFORMANCE (real measured data, use as soft guidance):\n" + "\n".join(lines)


def llm_analyze(
    provider: LLMProvider,
    segments: list[SegmentData],
    *,
    target_duration_ms: int = 45000,
    clip_count: int = 6,
    performance_hint: str = "",
) -> AnalysisResult:
    prompt = LLM_TEMPLATE.format(
        count=clip_count,
        seconds=target_duration_ms / 1000,
        transcript=transcript_for_prompt(segments),
        performance_context=performance_hint,
    )
    raw = provider.complete(LLM_SYSTEM, prompt, json_mode=True, max_tokens=3500)
    payload = extract_json(raw)
    clips_payload = payload.get("clips")
    if not isinstance(clips_payload, list) or not clips_payload:
        raise AIError("The AI provider returned no clips")
    total_ms = segments[-1].end_ms
    clips: list[ClipCandidate] = []
    for item in clips_payload[: max(1, clip_count) * 2]:
        try:
            start_ms = int(float(item.get("start_s", 0)) * 1000)
            end_ms = int(float(item.get("end_s", 0)) * 1000)
        except (TypeError, ValueError):
            continue
        start_ms = max(0, min(start_ms, total_ms - 2000))
        end_ms = max(start_ms + 2000, min(end_ms, total_ms))
        title = str(item.get("title") or "").strip()[:240]
        if not title:
            continue
        signals_raw = item.get("signals") if isinstance(item.get("signals"), dict) else {}
        signals = {
            str(key)[:32]: round(float(value), 1)
            for key, value in signals_raw.items()
            if isinstance(value, (int, float))
        }
        overlap = False
        for existing in clips:
            shared = max(0, min(end_ms, existing.end_ms) - max(start_ms, existing.start_ms))
            if shared > 0.25 * min(end_ms - start_ms, existing.end_ms - existing.start_ms):
                overlap = True
                break
        if overlap:
            continue
        clips.append(
            ClipCandidate(
                start_ms=start_ms,
                end_ms=end_ms,
                title=title,
                description=str(item.get("description") or "")[:1200],
                hook=str(item.get("hook") or "")[:300],
                transcript_text=_text_between(segments, start_ms, end_ms),
                explanation=str(item.get("explanation") or "Selected by the AI provider.")[:1200],
                virality_score=round(_clamp(float(item.get("virality_score", 60)) / 100) * 100, 1),
                engagement_potential=round(_clamp(float(item.get("engagement_potential", 60)) / 100) * 100, 1),
                signals=signals,
            )
        )
        if len(clips) >= clip_count:
            break
    if not clips:
        raise AIError("The AI provider's clips could not be validated against the transcript")
    topics = [str(t)[:40] for t in payload.get("topics", []) if isinstance(t, str)][:10]
    return AnalysisResult(
        summary=str(payload.get("summary") or "")[:2000],
        topics=topics,
        clips=clips,
        provider=provider.name,
        model=provider.model,
    )


def _text_between(segments: list[SegmentData], start_ms: int, end_ms: int) -> str:
    return " ".join(
        s.text.strip()
        for s in segments
        if s.end_ms > start_ms and s.start_ms < end_ms
    ).strip()


def analyze(
    db: Session,
    workspace_id: str,
    segments: list[SegmentData],
    *,
    provider: LLMProvider | None,
    target_duration_ms: int,
    clip_count: int,
    total_duration_ms: int | None = None,
) -> AnalysisResult:
    if provider is None:
        return heuristic_analyze(
            segments,
            target_duration_ms=target_duration_ms,
            clip_count=clip_count,
            total_duration_ms=total_duration_ms,
        )
    hint = performance_context(db, workspace_id)
    return llm_analyze(
        provider,
        segments,
        target_duration_ms=target_duration_ms,
        clip_count=clip_count,
        performance_hint=hint,
    )
