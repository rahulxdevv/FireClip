"""Discover public creators to add to a monitoring roster."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import RequestContext, get_context
from ..services import sources

router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.get("/streamers")
def discover_streamers(
    q: str = Query(min_length=2, max_length=120),
    live_only: bool = False,
    limit: int = Query(default=12, ge=1, le=20),
    ctx: RequestContext = Depends(get_context),
):
    """Search public live channels; no platform account or API key is required."""
    ctx.require("editor")
    if not sources.ytdlp_available():
        raise HTTPException(
            status_code=503,
            detail="Creator search needs yt-dlp on the server. Install it and retry.",
        )
    try:
        items = sources.search_streamers(q, limit=limit, live_only=live_only)
    except sources.SourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"query": q.strip(), "live_only": live_only, "items": items, "provider": "yt-dlp"}

