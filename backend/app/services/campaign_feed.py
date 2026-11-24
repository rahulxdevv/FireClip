"""Campaign discovery feeds.

Content Rewards platforms do not expose a single public endpoint that lists every
active campaign for every account. Instead of scraping a marketing site, this
module reads a JSON feed URL configured by the operator. The contract is small:
either a JSON list or an object with ``campaigns`` / ``data`` / ``items``.
"""
from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from ..config import settings


class CampaignFeedError(RuntimeError):
    pass


def configured() -> bool:
    return bool(settings.campaign_feed_url.strip())


def _safe_url(raw: str) -> str:
    value = raw.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise CampaignFeedError("Campaign feed URL must be an http(s) URL")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise CampaignFeedError("Campaign feed URL cannot point at a local host")
    addresses = []
    try:
        addresses.append(ipaddress.ip_address(host))
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(info[4][0])
                for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            ]
        except (OSError, ValueError) as exc:
            raise CampaignFeedError("Campaign feed host could not be resolved") from exc
    if not addresses:
        raise CampaignFeedError("Campaign feed host could not be resolved")
    if any(not address.is_global for address in addresses):
        raise CampaignFeedError("Campaign feed URL cannot point at a private network address")
    return value


def _text(value, limit: int = 4000) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(item) for item in value)
    return str(value).strip()[:limit]


def _tags(value) -> list[str]:
    if isinstance(value, str):
        items = value.replace(",", " ").split()
    elif isinstance(value, (list, tuple)):
        items = [str(item) for item in value]
    else:
        return []
    tags: list[str] = []
    for item in items:
        tag = item.strip()
        if not tag:
            continue
        tag = "#" + tag.lstrip("#")
        if tag.lower() not in {existing.lower() for existing in tags}:
            tags.append(tag[:60])
    return tags[:20]


def _one(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    external_id = _text(raw.get("id") or raw.get("campaign_id") or raw.get("slug"), 160)
    name = _text(raw.get("name") or raw.get("title"), 160)
    if not external_id or not name:
        return None
    status = _text(raw.get("status"), 24).lower() or "active"
    if status in {"ended", "expired", "closed", "paused", "draft", "archived"}:
        return None
    brand_raw = raw.get("brand") if isinstance(raw.get("brand"), dict) else {}
    brand = {
        key: brand_raw[key]
        for key in (
            "accent_color",
            "secondary_color",
            "font",
            "logo_text",
            "watermark",
            "cta",
            "headline",
            "hashtags",
            "logo_position",
            "headline_enabled",
        )
        if key in brand_raw
    }
    feed_tags = _tags(raw.get("hashtags") or raw.get("required_hashtags") or brand.get("hashtags"))
    if feed_tags:
        brand["hashtags"] = feed_tags
    guidelines = _text(raw.get("guidelines") or raw.get("rules") or raw.get("requirements") or raw.get("brief"), 4000)
    description = _text(raw.get("description") or raw.get("summary"), 2000)
    source_url = _text(raw.get("url") or raw.get("campaign_url"), 1000)
    if source_url and not source_url.startswith(("http://", "https://")):
        source_url = ""
    ends_at = raw.get("ends_at") or raw.get("end_date")
    if ends_at:
        try:
            parsed = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed <= datetime.now(timezone.utc):
                return None
        except ValueError:
            pass
    try:
        clip_count = max(1, min(20, int(raw.get("clip_count", raw.get("clips", 6)))))
    except (TypeError, ValueError):
        clip_count = 6
    try:
        min_score = max(0, min(100, int(raw.get("min_score", raw.get("quality_score", 0)))))
    except (TypeError, ValueError):
        min_score = 0
    try:
        target_ms = int(raw.get("target_duration_ms", 45000))
    except (TypeError, ValueError):
        target_ms = 45000
    target_ms = max(5000, min(180000, target_ms))
    return {
        "external_id": external_id,
        "name": name,
        "description": description,
        "brief": guidelines,
        "source_url": source_url,
        "brand": brand,
        "hashtags": feed_tags,
        "clip_count": clip_count,
        "min_score": min_score,
        "target_duration_ms": target_ms,
        "ends_at": _text(ends_at, 60),
    }


def normalize(payload) -> list[dict]:
    if isinstance(payload, dict):
        items = payload.get("campaigns") or payload.get("data") or payload.get("items")
        if isinstance(items, dict):
            items = items.get("campaigns") or items.get("data") or items.get("items")
        if items is None and isinstance(payload.get("id"), str):
            items = [payload]
    else:
        items = payload
    if not isinstance(items, list):
        raise CampaignFeedError("Campaign feed did not contain a list of campaigns")
    result: list[dict] = []
    seen: set[str] = set()
    for item in items:
        campaign = _one(item)
        if campaign and campaign["external_id"] not in seen:
            seen.add(campaign["external_id"])
            result.append(campaign)
    return result


def fetch() -> list[dict]:
    if not configured():
        raise CampaignFeedError(
            "No campaign feed is configured. Set CAMPAIGN_FEED_URL to a JSON feed from your "
            "Content Rewards provider, then restart the API."
        )
    url = _safe_url(settings.campaign_feed_url)
    headers = {"Accept": "application/json"}
    if settings.campaign_feed_token:
        headers["Authorization"] = f"Bearer {settings.campaign_feed_token}"
    try:
        response = httpx.get(url, headers=headers, timeout=20, follow_redirects=False)
    except httpx.HTTPError as exc:
        raise CampaignFeedError(f"Could not reach the campaign feed: {exc}") from exc
    if response.status_code >= 400:
        raise CampaignFeedError(f"Campaign feed returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise CampaignFeedError("Campaign feed did not return JSON") from exc
    return normalize(payload)
