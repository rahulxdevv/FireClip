"""Provider-agnostic LLM adapters.

Supported: OpenAI, Anthropic, Google Gemini, Ollama (local), plus a
deterministic heuristic engine that needs no credentials. Workspace-level keys
are encrypted at rest; environment keys are never sent to the browser.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AiProviderConfig
from ..security import decrypt_secret

logger = logging.getLogger("fireclip.ai")


class AIError(RuntimeError):
    pass


@dataclass
class ProviderInfo:
    provider: str
    label: str
    model: str
    base_url: str
    api_key: str
    local: bool = False

    @property
    def configured(self) -> bool:
        return self.local or bool(self.api_key)


class LLMProvider:
    name = "base"
    capabilities = ["chat", "json"]

    def __init__(self, info: ProviderInfo) -> None:
        self.info = info

    @property
    def model(self) -> str:
        return self.info.model

    def complete(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 2000) -> str:
        raise NotImplementedError

    def test(self) -> str:
        return self.complete("You are a health check.", "Reply with the single word OK.", max_tokens=16)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def complete(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 2000) -> str:
        payload: dict[str, Any] = {
            "model": self.info.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.4,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = httpx.post(
                f"{self.info.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.info.api_key}"},
                json=payload,
                timeout=settings.ai_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AIError(f"OpenAI request failed: {exc}") from exc
        if response.status_code >= 400:
            raise AIError(f"OpenAI error {response.status_code}: {response.text[:400]}")
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as exc:
            raise AIError("OpenAI returned an unexpected response shape") from exc


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def complete(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 2000) -> str:
        try:
            response = httpx.post(
                f"{self.info.base_url.rstrip('/')}/v1/messages",
                headers={
                    "x-api-key": self.info.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.info.model,
                    "max_tokens": max_tokens,
                    "temperature": 0.4,
                    "system": system + ("\nRespond with a single valid JSON object." if json_mode else ""),
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=settings.ai_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AIError(f"Anthropic request failed: {exc}") from exc
        if response.status_code >= 400:
            raise AIError(f"Anthropic error {response.status_code}: {response.text[:400]}")
        data = response.json()
        parts = data.get("content") or []
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        if not text:
            raise AIError("Anthropic returned an empty response")
        return text


class GeminiProvider(LLMProvider):
    name = "gemini"

    def complete(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 2000) -> str:
        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": max_tokens},
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        try:
            response = httpx.post(
                f"{self.info.base_url.rstrip('/')}/models/{self.info.model}:generateContent",
                params={"key": self.info.api_key},
                json=payload,
                timeout=settings.ai_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AIError(f"Gemini request failed: {exc}") from exc
        if response.status_code >= 400:
            raise AIError(f"Gemini error {response.status_code}: {response.text[:400]}")
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise AIError("Gemini returned an unexpected response shape") from exc


class OllamaProvider(LLMProvider):
    name = "ollama"

    def complete(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 2000) -> str:
        payload: dict[str, Any] = {
            "model": self.info.model,
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": max_tokens},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["format"] = "json"
        try:
            response = httpx.post(
                f"{self.info.base_url.rstrip('/')}/api/chat",
                json=payload,
                timeout=settings.ai_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AIError(
                f"Ollama request failed ({self.info.base_url}). Is `ollama serve` running? {exc}"
            ) from exc
        if response.status_code >= 400:
            raise AIError(f"Ollama error {response.status_code}: {response.text[:300]}")
        data = response.json()
        message = data.get("message") or {}
        if not message.get("content"):
            raise AIError("Ollama returned an empty response")
        return message["content"]


PROVIDERS = {
    "openai": (OpenAIProvider, "OpenAI", settings.openai_model, settings.openai_base_url, settings.openai_api_key, False, ["chat", "json", "vision"]),
    "anthropic": (AnthropicProvider, "Anthropic", settings.anthropic_model, settings.anthropic_base_url, settings.anthropic_api_key, False, ["chat", "json"]),
    "gemini": (GeminiProvider, "Google Gemini", settings.gemini_model, settings.gemini_base_url, settings.gemini_api_key, False, ["chat", "json", "vision"]),
    "ollama": (OllamaProvider, "Ollama (local)", settings.ollama_model, settings.ollama_base_url, "local", True, ["chat", "json"]),
}


def provider_infos(db: Session, workspace_id: str | None) -> list[ProviderInfo]:
    configs: dict[str, AiProviderConfig] = {}
    if workspace_id:
        for row in db.scalars(select(AiProviderConfig).where(AiProviderConfig.workspace_id == workspace_id)):
            configs[row.provider] = row
    infos: list[ProviderInfo] = []
    for slug, (_cls, label, model, base_url, env_key, local, _caps) in PROVIDERS.items():
        row = configs.get(slug)
        api_key = env_key
        if row and row.api_key_encrypted:
            api_key = decrypt_secret(row.api_key_encrypted) or api_key
        infos.append(
            ProviderInfo(
                provider=slug,
                label=label,
                model=(row.model if row and row.model else model),
                base_url=(row.base_url if row and row.base_url else base_url),
                api_key=api_key,
                local=local,
            )
        )
    return infos


def build_provider(db: Session, workspace_id: str | None, requested: str = "auto") -> LLMProvider | None:
    """Return an LLM provider or None to signal 'use the heuristic engine'."""
    infos = {info.provider: info for info in provider_infos(db, workspace_id)}
    default_row = None
    if workspace_id:
        default_row = db.scalar(
            select(AiProviderConfig).where(
                AiProviderConfig.workspace_id == workspace_id, AiProviderConfig.is_default.is_(True)
            )
        )
    choice = requested
    if requested == "heuristic":
        return None
    if requested == "auto":
        if settings.ai_provider != "auto":
            choice = settings.ai_provider
        elif default_row and default_row.enabled:
            choice = default_row.provider
        else:
            # Ollama is only used when explicitly selected (env/provider default),
            # never as an implicit auto choice that could fail on a missing server.
            for slug in ("openai", "anthropic", "gemini"):
                if infos[slug].configured:
                    choice = slug
                    break
            else:
                return None
    info = infos.get(choice)
    if not info:
        raise AIError(f"Unknown AI provider '{choice}'")
    row = db.scalar(
        select(AiProviderConfig).where(
            AiProviderConfig.workspace_id == workspace_id, AiProviderConfig.provider == choice
        )
    ) if workspace_id else None
    if row and not row.enabled:
        raise AIError(f"The {info.label} provider is disabled in AI settings")
    if not info.configured:
        raise AIError(
            f"{info.label} is not configured. Add an API key in AI settings or choose the built-in "
            "heuristic engine. Providers never fall back silently."
        )
    cls = PROVIDERS[choice][0]
    return cls(info)


def test_provider(db: Session, workspace_id: str, provider: str) -> tuple[bool, str, int]:
    if provider == "heuristic":
        return True, "Heuristic engine is always available (no network, no API key).", 0
    try:
        instance = build_provider(db, workspace_id, provider)
    except AIError as exc:
        return False, str(exc), 0
    if instance is None:
        return False, "Provider is not configured.", 0
    started = time.monotonic()
    try:
        output = instance.test()
        latency = int((time.monotonic() - started) * 1000)
        return True, f"Connected. Response: {output.strip()[:120]}", latency
    except AIError as exc:
        return False, str(exc), int((time.monotonic() - started) * 1000)


def extract_json(text: str) -> dict:
    """Parse JSON from model output, tolerating code fences and preamble."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise AIError("The AI provider did not return valid JSON")
