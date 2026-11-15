"""Per-clip social content generation (titles, captions, hashtags, CTAs)."""
from __future__ import annotations

import re

from ..models import CandidateClip, SourceVideo
from .ai import AIError, LLMProvider, extract_json
from .highlights import transcript_for_prompt
from .transcription import SegmentData

PLATFORM_LIMITS = {"youtube": 5000, "tiktok": 2200, "instagram": 2200, "facebook": 63206}
GENERIC_TAGS = ["#shorts", "#reels", "#fyp", "#creator", "#podcast"]

SYSTEM = """You are a short-form social strategist. You write honest, specific copy that matches the
clip's actual content. Never invent facts, numbers or quotes that are not in the transcript.
Return only JSON."""

PROMPT = """Create social copy for this clip.

Video: {video_title}
Clip title: {clip_title}
Duration: {duration}s
Transcript excerpt:
{transcript}

Return JSON with:
- titles: 5 options (max 70 chars each)
- hooks: 4 spoken hooks (max 18 words)
- descriptions: 3 options (max 240 chars)
- hashtags: 10 relevant hashtags, lowercase, no spaces
- captions: object with youtube, tiktok, instagram, facebook keys, each platform-appropriate
- thumbnail_ideas: 3 concrete visual ideas
- calls_to_action: 3 options
- summary: 2 sentence summary of the clip
"""


def _keywords(text: str, limit: int = 8) -> list[str]:
    stop = set("this that with from have will your just they what when more about into than then there their would could should really very much some make made here".split())
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text)]
    counts: dict[str, int] = {}
    for word in words:
        if word not in stop:
            counts[word] = counts.get(word, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]]


def heuristic_content(clip: CandidateClip, video: SourceVideo) -> dict:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clip.transcript_text) if s.strip()]
    keywords = _keywords(clip.transcript_text or clip.title)
    topic = keywords[0] if keywords else "this"
    second = keywords[1] if len(keywords) > 1 else topic
    first = sentences[0] if sentences else clip.hook or clip.title
    stat = next((s for s in sentences if re.search(r"\d", s)), "")
    titles = [
        clip.title,
        f"The {topic} mistake most people never notice",
        f"Why {topic} changes everything",
        f"Stop doing this with {second}",
        f"What nobody tells you about {topic}",
    ]
    deduped: list[str] = []
    for title in titles:
        title = title[:70].strip()
        if title and title.lower() not in {t.lower() for t in deduped}:
            deduped.append(title)
    hashtags = [f"#{k}" for k in keywords[:6]] + GENERIC_TAGS
    hashtags = list(dict.fromkeys(tag for tag in hashtags if len(tag) > 2))[:10]
    base_description = (clip.description or first)[:200]
    summary = f"{first[:180]} {sentences[1][:120] if len(sentences) > 1 else ''}".strip()
    captions = {
        "youtube": f"{deduped[0]}\n\n{base_description}\n\n{' '.join(hashtags[:5])}",
        "tiktok": f"{deduped[1] if len(deduped) > 1 else deduped[0]}\n\n{base_description} {' '.join(hashtags[:6])}",
        "instagram": f"{deduped[0]}\n\n{base_description}\n\n{' '.join(hashtags[:8])}",
        "facebook": f"{base_description}\n\n{' '.join(hashtags[:4])}",
    }
    return {
        "titles": deduped,
        "hooks": [
            first[:140],
            f"Here is the part about {topic} nobody talks about.",
            stat[:140] if stat else f"The fastest way to understand {topic}.",
            f"What would change if you applied this to {second}?",
        ],
        "descriptions": [
            base_description,
            f"{first[:150]} Full clip inside.".strip(),
            f"A {round(clip.duration_ms / 1000)} second breakdown of {topic}.",
        ],
        "hashtags": hashtags,
        "captions": captions,
        "thumbnail_ideas": [
            f"Close-up of the speaker with the phrase \"{topic}\" in orange.",
            "Split frame: calm before / result after, with a bold number overlay.",
            "Freeze-frame on the strongest gesture with a short question as the title.",
        ],
        "calls_to_action": [
            "Follow for more clips like this.",
            "Save this before you forget it.",
            "Comment your take below.",
        ],
        "summary": summary or base_description,
        "provider": "heuristic",
        "model": "fireclip-copy-v1",
    }


def llm_content(
    provider: LLMProvider,
    clip: CandidateClip,
    segments: list[SegmentData],
    video: SourceVideo,
) -> dict:
    excerpt = transcript_for_prompt(
        [s for s in segments if s.end_ms > clip.start_ms and s.start_ms < clip.end_ms], max_chars=9000
    )
    prompt = PROMPT.format(
        video_title=video.title,
        clip_title=clip.title,
        duration=round(clip.duration_ms / 1000),
        transcript=excerpt or clip.transcript_text[:6000],
    )
    raw = provider.complete(SYSTEM, prompt, json_mode=True, max_tokens=1800)
    payload = extract_json(raw)
    result = heuristic_content(clip, video)
    for key in ("titles", "hooks", "descriptions", "thumbnail_ideas", "calls_to_action"):
        value = payload.get(key)
        if isinstance(value, list):
            cleaned = [str(item).strip()[:400] for item in value if str(item).strip()]
            if cleaned:
                result[key] = cleaned
    hashtags = payload.get("hashtags")
    if isinstance(hashtags, list):
        tags = []
        for tag in hashtags[:12]:
            tag = str(tag).strip()
            if not tag:
                continue
            tags.append(tag if tag.startswith("#") else f"#{tag.lstrip('#')}")
        if tags:
            result["hashtags"] = tags
    captions = payload.get("captions")
    if isinstance(captions, dict):
        for platform, limit in PLATFORM_LIMITS.items():
            if isinstance(captions.get(platform), str) and captions[platform].strip():
                result["captions"][platform] = captions[platform].strip()[:limit]
    if isinstance(payload.get("summary"), str) and payload["summary"].strip():
        result["summary"] = payload["summary"].strip()[:800]
    result["provider"] = provider.name
    result["model"] = provider.model
    return result


def generate(
    provider: LLMProvider | None,
    clip: CandidateClip,
    segments: list[SegmentData],
    video: SourceVideo,
) -> dict:
    if provider is None:
        return heuristic_content(clip, video)
    try:
        return llm_content(provider, clip, segments, video)
    except AIError:
        raise
