"""Outbound webhooks with HMAC signatures and a delivery log."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from ..models import WebhookDelivery, WebhookEndpoint
from .sources import validate_url

logger = logging.getLogger("fireclip.webhooks")

EVENTS = [
    "clip.approved",
    "clip.rejected",
    "clip.rendered",
    "clip.published",
    "share.created",
    "video.ready",
]


def _signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _send(endpoint_id: str, url: str, secret: str, payload: dict, delivery_id: str | None = None) -> tuple[int, str]:
    body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "FireClip-Webhooks/1.1",
        "X-FireClip-Event": payload.get("type", ""),
        "X-FireClip-Delivery": payload.get("id", ""),
    }
    if secret:
        headers["X-FireClip-Signature"] = _signature(secret, body)
    started = time.perf_counter()
    status_code = 0
    error = ""
    # Three in-process attempts with a short backoff. Retry transport failures,
    # rate limits and server errors; a 4xx will not improve on its own.
    for attempt in range(3):
        try:
            response = httpx.post(
                url, content=body, headers=headers, timeout=10, follow_redirects=False
            )
            status_code = response.status_code
            if 200 <= status_code < 300:
                error = ""
                break
            error = f"Endpoint returned HTTP {status_code}: {response.text[:200]}"
            if status_code < 500 and status_code != 429:
                break
        except Exception as exc:
            status_code = 0
            error = str(exc)[:500]
        if attempt < 2:
            time.sleep(2**attempt)
    duration = int((time.perf_counter() - started) * 1000)
    if delivery_id:
        from ..database import session_scope

        try:
            with session_scope() as db:
                delivery = db.get(WebhookDelivery, delivery_id)
                if delivery:
                    delivery.status_code = status_code
                    delivery.ok = 200 <= status_code < 300
                    delivery.error = error
                    delivery.duration_ms = duration
        except Exception:
            logger.exception("Could not record webhook delivery %s", delivery_id)
    return status_code, error


def emit(db, workspace_id: str, event: str, data: dict) -> int:
    """Queue an event to all matching endpoints. Returns the number queued."""
    endpoints = list(
        db.scalars(
            select(WebhookEndpoint).where(
                WebhookEndpoint.workspace_id == workspace_id, WebhookEndpoint.enabled.is_(True)
            )
        )
    )
    targets = [row for row in endpoints if not row.events or "*" in row.events or event in row.events]
    if not targets:
        return 0
    envelope = {
        "id": f"evt_{uuid.uuid4().hex[:20]}",
        "type": event,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    queued = []
    for endpoint in targets:
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            workspace_id=workspace_id,
            event=event,
            payload=envelope,
        )
        db.add(delivery)
        db.flush()
        queued.append((delivery.id, endpoint.id, endpoint.url, endpoint.secret or ""))
    db.commit()
    for delivery_id, endpoint_id, url, secret in queued:
        thread = threading.Thread(
            target=_send,
            args=(endpoint_id, url, secret, envelope, delivery_id),
            name=f"webhook-{endpoint_id[:6]}",
            daemon=True,
        )
        thread.start()
    return len(queued)


def test_endpoint(endpoint: WebhookEndpoint, event: str = "webhook.test") -> tuple[int, str]:
    payload = {
        "id": f"evt_{uuid.uuid4().hex[:20]}",
        "type": event,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": {"message": "This is a test delivery from FireClip."},
    }
    return _send(endpoint.id, endpoint.url, endpoint.secret or "", payload)


def validate_endpoint_url(url: str) -> str:
    return validate_url(url)
