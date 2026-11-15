"""Analytics overview, sync and manual measurement entry."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import RequestContext, get_context, rate_limit
from ..schemas import AnalyticsEntry, AnalyticsOverview, AnalyticsSyncOut
from ..services import analytics as analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def overview(ctx: RequestContext = Depends(get_context)):
    return analytics_service.overview(ctx.db, ctx.workspace.id)


@router.post("/sync", response_model=AnalyticsSyncOut)
def sync(
    ctx: RequestContext = Depends(get_context),
    _limit=Depends(rate_limit("analytics-sync", 10)),
):
    ctx.require("editor")
    return analytics_service.sync(ctx.db, ctx.workspace.id, ctx.user.id)


@router.post("/entry", status_code=201)
def add_entry(payload: AnalyticsEntry, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    try:
        record = analytics_service.add_manual(ctx.db, ctx.workspace.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": record.id,
        "publishing_job_id": record.publishing_job_id,
        "views": record.views,
        "likes": record.likes,
        "comments": record.comments,
        "shares": record.shares,
        "retention_pct": record.retention_pct,
        "source": record.source,
        "captured_at": record.captured_at,
    }
