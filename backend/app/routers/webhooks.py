"""Workspace webhook management."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from ..deps import RequestContext, get_context, record_audit
from ..models import WebhookDelivery, WebhookEndpoint
from ..schemas import WebhookCreate, WebhookOut, WebhookUpdate
from ..services import webhooks as hook_service
from ..services.sources import SourceError

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _out(endpoint: WebhookEndpoint) -> WebhookOut:
    return WebhookOut(
        id=endpoint.id,
        url=endpoint.url,
        description=endpoint.description,
        events=endpoint.events or ["*"],
        enabled=endpoint.enabled,
        secret=endpoint.secret,
        created_at=endpoint.created_at,
    )


def _validate_events(events: list[str]) -> list[str]:
    clean = [event.strip() for event in events if event.strip()]
    if not clean:
        return ["*"]
    unknown = [event for event in clean if event != "*" and event not in hook_service.EVENTS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown event: {unknown[0]}")
    return sorted(set(clean))


def _get(ctx: RequestContext, endpoint_id: str) -> WebhookEndpoint:
    endpoint = ctx.db.get(WebhookEndpoint, endpoint_id)
    if not endpoint or endpoint.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return endpoint


@router.get("")
def list_webhooks(ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    rows = ctx.db.scalars(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.workspace_id == ctx.workspace.id)
        .order_by(WebhookEndpoint.created_at.desc())
    )
    return {
        "events": hook_service.EVENTS,
        "endpoints": [_out(row) for row in rows],
    }


@router.post("", response_model=WebhookOut, status_code=201)
def create_webhook(payload: WebhookCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    try:
        url = hook_service.validate_endpoint_url(payload.url)
    except SourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    endpoint = WebhookEndpoint(
        workspace_id=ctx.workspace.id,
        url=url,
        description=payload.description.strip(),
        events=_validate_events(payload.events),
        enabled=payload.enabled,
        secret="whsec_" + secrets.token_urlsafe(24),
    )
    ctx.db.add(endpoint)
    record_audit(
        ctx.db,
        "webhook.create",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="webhook",
        target_id=endpoint.id,
        ip_address=ctx.ip_address,
    )
    ctx.db.commit()
    ctx.db.refresh(endpoint)
    return _out(endpoint)


@router.patch("/{endpoint_id}", response_model=WebhookOut)
def update_webhook(endpoint_id: str, payload: WebhookUpdate, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    endpoint = _get(ctx, endpoint_id)
    if payload.url is not None:
        try:
            endpoint.url = hook_service.validate_endpoint_url(payload.url)
        except SourceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.description is not None:
        endpoint.description = payload.description.strip()
    if payload.events is not None:
        endpoint.events = _validate_events(payload.events)
    if payload.enabled is not None:
        endpoint.enabled = payload.enabled
    ctx.db.commit()
    ctx.db.refresh(endpoint)
    return _out(endpoint)


@router.delete("/{endpoint_id}", status_code=204)
def delete_webhook(endpoint_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    endpoint = _get(ctx, endpoint_id)
    ctx.db.delete(endpoint)
    ctx.db.commit()


@router.post("/{endpoint_id}/test")
def test_webhook(endpoint_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    endpoint = _get(ctx, endpoint_id)
    status_code, error = hook_service.test_endpoint(endpoint)
    return {"ok": 200 <= status_code < 300, "status_code": status_code, "error": error}


@router.get("/{endpoint_id}/deliveries")
def deliveries(
    endpoint_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    ctx: RequestContext = Depends(get_context),
):
    ctx.require("admin")
    endpoint = _get(ctx, endpoint_id)
    rows = ctx.db.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == endpoint.id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": row.id,
            "event": row.event,
            "ok": row.ok,
            "status_code": row.status_code,
            "error": row.error,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at,
        }
        for row in rows
    ]
