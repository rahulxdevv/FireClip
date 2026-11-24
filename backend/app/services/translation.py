"""Transcript translation for burned-in multilingual captions.

Uses the workspace LLM provider. There is no offline machine-translation model
bundled, so an unconfigured workspace gets an explicit error rather than a fake
translation.
"""
from __future__ import annotations

import json

from ..models import TranscriptSegment
from .ai import AIError, LLMProvider, extract_json


LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "hi": "Hindi",
    "ur": "Urdu",
    "bn": "Bengali",
    "ar": "Arabic",
    "tr": "Turkish",
    "id": "Indonesian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese (Simplified)",
    "ru": "Russian",
    "vi": "Vietnamese",
    "th": "Thai",
    "pl": "Polish",
}

SYSTEM = (
    "You translate short-form video captions. Preserve meaning, names, numbers and tone. "
    "Return only the requested JSON. Never add commentary."
)


class TranslationError(RuntimeError):
    pass


def language_name(code: str) -> str:
    return LANGUAGES.get(code.lower(), code)


def translate_segments(
    provider: LLMProvider | None,
    segments: list[TranscriptSegment],
    language: str,
    batch_size: int = 35,
) -> dict:
    if provider is None:
        raise TranslationError(
            "Caption translation needs an AI provider. Configure one in AI settings or keep the original language."
        )
    target = language_name(language)
    translated: list[dict] = []
    for start in range(0, len(segments), batch_size):
        batch = segments[start : start + batch_size]
        numbered = [
            {"index": index, "text": segment.text.strip()}
            for index, segment in enumerate(batch)
        ]
        prompt = (
            f"Translate these {len(batch)} caption lines into {target}.\n"
            f"Keep every line short enough to read on screen. Translate each item independently.\n"
            f"Clipping context: the transcript may cut off at the start or end.\n\n"
            f"{json.dumps(numbered, ensure_ascii=False)}\n\n"
            'Return JSON exactly as {"translations": ["line 1", "line 2", ...]} with '
            f"{len(batch)} items in the same order."
        )
        try:
            raw = provider.complete(SYSTEM, prompt, json_mode=True, max_tokens=min(4000, 400 + len(batch) * 90))
            payload = extract_json(raw)
        except AIError as exc:
            raise TranslationError(str(exc)) from exc
        values = payload.get("translations") if isinstance(payload, dict) else None
        if not isinstance(values, list) or len(values) != len(batch):
            raise TranslationError("The AI provider returned an incomplete translation. Try again.")
        for segment, value in zip(batch, values):
            text = str(value).strip()
            if not text:
                raise TranslationError("The AI provider returned an empty caption line. Try again.")
            translated.append(
                {
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                    "text": text[:1000],
                }
            )
    return {
        "language": language.lower(),
        "language_name": target,
        "provider": provider.name,
        "model": provider.model,
        "segments": translated,
    }
