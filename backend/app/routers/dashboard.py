"""Dashboard aggregation, notifications, billing and system diagnostics."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select

from ..config import settings
from ..deps import RequestContext, get_context, record_audit
from ..models import (
    AuditLog,
    BillingInvoice,
    CandidateClip,
    ExportedVideo,
    Notification,
    PipelineJob,
    PublishingJob,
    RenderJob,
    SourceVideo,
    UsageRecord,
    User,
)
from ..schemas import DashboardOut, NotificationOut, SystemStatus
from ..services import billing, media, publishing as pub_service, storage_guard, transcription
from ..services.ai import PROVIDERS
from ..storage import get_storage
from .common import clip_out, render_out, video_out

logger = logging.getLogger("fireclip.dashboard")

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(ctx: RequestContext = Depends(get_context)):
    db = ctx.db
    wid = ctx.workspace.id

    def count(model) -> int:
        return db.scalar(select(func.count()).select_from(model).where(model.workspace_id == wid)) or 0

    active_jobs = list(
        db.scalars(
            select(PipelineJob)
            .where(PipelineJob.workspace_id == wid, PipelineJob.status.in_(["queued", "running"]))
            .order_by(PipelineJob.created_at.desc())
            .limit(8)
        )
    )
    recent_videos = list(
        db.scalars(
            select(SourceVideo).where(SourceVideo.workspace_id == wid).order_by(SourceVideo.created_at.desc()).limit(5)
        )
    )
    recent_clips = list(
        db.scalars(
            select(CandidateClip)
            .where(CandidateClip.workspace_id == wid)
            .order_by(CandidateClip.created_at.desc())
            .limit(5)
        )
    )
    videos = {
        video.id: video
        for video in db.scalars(
            select(SourceVideo).where(SourceVideo.id.in_({clip.video_id for clip in recent_clips}))
        )
    } if recent_clips else {}
    activity_rows = db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.workspace_id == wid)
        .order_by(AuditLog.created_at.desc())
        .limit(8)
    ).all()
    recent_renders = list(
        db.scalars(
            select(RenderJob).where(RenderJob.workspace_id == wid).order_by(RenderJob.created_at.desc()).limit(5)
        )
    )
    notifications = list(
        db.scalars(
            select(Notification)
            .where(
                Notification.workspace_id == wid,
                or_(Notification.user_id.is_(None), Notification.user_id == ctx.user.id),
            )
            .order_by(Notification.created_at.desc())
            .limit(8)
        )
    )
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage_rows = db.execute(
        select(UsageRecord.kind, func.coalesce(func.sum(UsageRecord.quantity), 0))
        .where(UsageRecord.workspace_id == wid, UsageRecord.created_at >= month_start)
        .group_by(UsageRecord.kind)
    ).all()
    usage = {kind: float(total or 0) for kind, total in usage_rows}
    storage_used = sum(video.size_bytes or 0 for video in recent_videos)
    total_storage = db.scalar(
        select(func.coalesce(func.sum(SourceVideo.size_bytes), 0)).where(SourceVideo.workspace_id == wid)
    ) or 0
    processing = [
        {
            "id": job.id,
            "video_id": job.video_id,
            "kind": job.kind,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "error_message": job.error_message,
            "created_at": job.created_at,
        }
        for job in active_jobs
    ]
    return {
        "counts": {
            "videos": count(SourceVideo),
            "clips": count(CandidateClip),
            "approved_clips": db.scalar(
                select(func.count()).select_from(CandidateClip).where(
                    CandidateClip.workspace_id == wid, CandidateClip.status == "approved"
                )
            ) or 0,
            "processing": len(active_jobs),
            "published": db.scalar(
                select(func.count()).select_from(PublishingJob).where(
                    PublishingJob.workspace_id == wid, PublishingJob.status == "published"
                )
            ) or 0,
            "renders": count(RenderJob),
            "exports": count(ExportedVideo),
            "scheduled_posts": db.scalar(
                select(func.count()).select_from(PublishingJob).where(
                    PublishingJob.workspace_id == wid, PublishingJob.status == "scheduled"
                )
            ) or 0,
        },
        "storage_bytes": int(total_storage),
        "processing": processing,
        "recent_videos": [video_out(video) for video in recent_videos],
        "recent_clips": [clip_out(clip, videos.get(clip.video_id)) for clip in recent_clips],
        "recent_activity": [
            {
                "id": log.id,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "user_email": email,
                "created_at": log.created_at,
                "meta": log.meta or {},
            }
            for log, email in activity_rows
        ],
        "usage": {
            "transcription_seconds": usage.get("transcription", 0),
            "ai_units": usage.get("ai", 0),
            "render_seconds": usage.get("render_seconds", 0),
            "storage_gb": round(int(total_storage) / (1024**3), 2),
            "recent_storage_bytes": storage_used,
        },
        "renders": [
            render_out(
                render,
                db.scalar(select(ExportedVideo).where(ExportedVideo.render_job_id == render.id)),
            )
            for render in recent_renders
        ],
        "notifications": [NotificationOut.model_validate(note) for note in notifications],
    }


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    ctx: RequestContext = Depends(get_context),
):
    query = select(Notification).where(
        Notification.workspace_id == ctx.workspace.id,
        or_(Notification.user_id.is_(None), Notification.user_id == ctx.user.id),
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return list(ctx.db.scalars(query.order_by(Notification.created_at.desc()).limit(limit)))


@router.post("/notifications/read-all", status_code=204)
def read_all(ctx: RequestContext = Depends(get_context)):
    now = datetime.now(timezone.utc)
    for note in ctx.db.scalars(
        select(Notification).where(
            Notification.workspace_id == ctx.workspace.id,
            or_(Notification.user_id.is_(None), Notification.user_id == ctx.user.id),
            Notification.read_at.is_(None),
        )
    ):
        note.read_at = now
    ctx.db.commit()


@router.post("/notifications/{notification_id}/read", status_code=204)
def read_one(notification_id: str, ctx: RequestContext = Depends(get_context)):
    note = ctx.db.get(Notification, notification_id)
    if not note or note.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    note.read_at = datetime.now(timezone.utc)
    ctx.db.commit()


@router.get("/system/status", response_model=SystemStatus)
def system_status(ctx: RequestContext = Depends(get_context)):
    import shutil

    engines = transcription.engine_status()
    providers = {}
    for info in __import__("app.services.ai", fromlist=["provider_infos"]).provider_infos(ctx.db, ctx.workspace.id):
        providers[info.provider] = {
            "label": PROVIDERS[info.provider][1],
            "configured": info.configured,
            "model": info.model,
            "local": info.local,
        }
    redis_ok = False
    if settings.redis_url:
        try:
            import redis

            redis_ok = bool(redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping())
        except Exception:
            redis_ok = False
    return {
        "ffmpeg": media.ffmpeg_available(),
        "ffmpeg_version": media.ffmpeg_version(),
        "transcription_engines": engines,
        "ai_providers": providers,
        "redis": redis_ok,
        "storage": settings.storage_backend,
        "database": settings.database_url.split("://", 1)[0],
        "job_runner": "arq" if settings.use_arq else "inline",
        "ytdlp": __import__("app.services.sources", fromlist=["ytdlp_available"]).ytdlp_available(),
        "workspace_storage_bytes": storage_guard.workspace_bytes(ctx.db, ctx.workspace.id),
        "disk_free_gb": (
            round(shutil.disk_usage(settings.data_dir).free / storage_guard.GIGABYTE, 2)
            if settings.storage_backend.lower() != "s3"
            else None
        ),
    }


@router.get("/billing")
def billing_overview(ctx: RequestContext = Depends(get_context)):
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    workspace = ctx.workspace
    render_seconds = ctx.db.scalar(
        select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
            UsageRecord.workspace_id == workspace.id,
            UsageRecord.kind == "render_seconds",
            UsageRecord.created_at >= month_start,
        )
    ) or 0
    clips_this_month = ctx.db.scalar(
        select(func.count()).select_from(CandidateClip).where(
            CandidateClip.workspace_id == workspace.id, CandidateClip.created_at >= month_start
        )
    ) or 0
    usage_rows = ctx.db.execute(
        select(UsageRecord.kind, UsageRecord.provider, func.sum(UsageRecord.quantity))
        .where(UsageRecord.workspace_id == workspace.id, UsageRecord.created_at >= month_start)
        .group_by(UsageRecord.kind, UsageRecord.provider)
        .order_by(func.sum(UsageRecord.quantity).desc())
    ).all()
    upload_bytes = ctx.db.scalar(
        select(func.coalesce(func.sum(SourceVideo.size_bytes), 0)).where(
            SourceVideo.workspace_id == workspace.id
        )
    ) or 0
    export_bytes = ctx.db.scalar(
        select(func.coalesce(func.sum(ExportedVideo.size_bytes), 0)).where(
            ExportedVideo.workspace_id == workspace.id
        )
    ) or 0
    invoices = ctx.db.scalars(
        select(BillingInvoice)
        .where(BillingInvoice.workspace_id == workspace.id)
        .order_by(BillingInvoice.created_at.desc())
        .limit(12)
    ).all()
    plan = billing.PLAN_INDEX.get(workspace.plan, billing.PLAN_INDEX[billing.DEFAULT_PLAN])
    return {
        "plan": workspace.plan,
        "plan_name": plan["name"],
        "status": workspace.plan_status,
        "interval": workspace.plan_interval,
        "renews_at": workspace.plan_renews_at,
        "limits": {
            "clips_per_month": workspace.monthly_clip_limit,
            "render_minutes_per_month": workspace.monthly_render_minutes,
        },
        "usage": {
            "clips_this_month": clips_this_month,
            "render_minutes_this_month": round(float(render_seconds) / 60, 1),
            "breakdown": [
                {
                    "kind": kind,
                    "provider": provider or "local",
                    "quantity": round(float(quantity or 0), 2),
                }
                for kind, provider, quantity in usage_rows
            ],
            "storage_bytes": int(upload_bytes) + int(export_bytes),
            "upload_bytes": int(upload_bytes),
            "export_bytes": int(export_bytes),
        },
        "plans": billing.PLANS,
        "payment_provider": billing.provider_status(),
        "invoices": [
            {
                "id": row.id,
                "number": row.number,
                "status": row.status,
                "amount_cents": row.amount_cents,
                "currency": row.currency,
                "hosted_url": row.hosted_url,
                "pdf_url": row.pdf_url,
                "period_start": row.period_start,
                "period_end": row.period_end,
                "created_at": row.created_at,
            }
            for row in invoices
        ],
    }


@router.get("/health")
def health():
    return {"status": "ok", "service": "fireclip-api", "environment": settings.environment}


@router.get("/health/ready")
def readiness():
    checks = {"database": False, "ffmpeg": media.ffmpeg_available(), "storage": False}
    try:
        from ..database import engine

        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        checks["database"] = True
    except Exception:
        checks["database"] = False
    try:
        checks["storage"] = get_storage().exists("") is not None
    except Exception:
        checks["storage"] = False
    ready = checks["database"] and checks["ffmpeg"]
    return {"ready": ready, "checks": checks}