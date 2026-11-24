"""FireClip API application."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db
from .jobs import load_tasks, recover_interrupted_jobs, set_arq_pool
from .routers import (
    ai,
    analytics,
    assets,
    auth,
    billing,
    campaigns,
    clips,
    dashboard,
    editors,
    live,
    projects,
    publishing,
    renders,
    shares,
    videos,
    webhooks,
    workspaces,
)
from .scheduler import start_inline_scheduler, stop_scheduler
from .seed import seed_builtin_caption_styles

log_level = os.getenv("LOG_LEVEL", "DEBUG" if settings.debug else "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("fireclip")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FireClip API (%s)", settings.environment)
    if settings.auto_migrate:
        init_db()
    seed_builtin_caption_styles()
    load_tasks()
    queue_ready = False
    if settings.use_arq:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            set_arq_pool(pool, asyncio.get_running_loop())
            queue_ready = True
            logger.info("Connected to Redis job queue")
        except Exception:
            logger.exception("Could not connect to Redis; jobs will run inline")
    if not queue_ready:
        # With a durable ARQ queue, queued jobs belong to the worker and must
        # survive an API restart. Only the inline runner needs crash recovery.
        fixed = recover_interrupted_jobs()
        if fixed:
            logger.warning("Marked %s interrupted jobs as failed", fixed)
        start_inline_scheduler()
        logger.info("Inline scheduler started")
    yield
    stop_scheduler()
    logger.info("FireClip API stopped")


app = FastAPI(
    title="FireClip API",
    version="1.0.0",
    description="AI video clipping platform: ingest, transcribe, analyse, edit, render, publish.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys([*settings.cors_origins, settings.frontend_url])),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Workspace-Id", "X-API-Key", "Range"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    origin = request.headers.get("origin")
    if (
        origin
        and request.method not in SAFE_METHODS
        and origin not in set(settings.cors_origins) | {settings.frontend_url}
        and settings.environment == "production"
    ):
        logger.warning("Blocked origin %s for %s %s (request %s)", origin, request.method, request.url.path, request_id)
        return JSONResponse(
            {"detail": "Origin not allowed", "request_id": request_id},
            status_code=403,
            headers={"X-Request-ID": request_id},
        )
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled API error: %s %s (request %s)",
            request.method,
            request.url.path,
            request_id,
        )
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("X-FireClip-Version", "1.0.0")
    if request.url.path not in {"/health", "/api/health"}:
        logger.info(
            "%s %s -> %s %.1fms (request %s)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
    return response


for module in (auth, workspaces, projects, campaigns, videos, assets, clips, editors, renders, publishing, analytics, ai, dashboard, billing, shares, webhooks, live):
    app.include_router(module.router)


@app.get("/api", include_in_schema=False)
def api_root():
    return {
        "name": "FireClip API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "service": "fireclip-api", "environment": settings.environment}