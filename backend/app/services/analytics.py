"""Analytics aggregation.

Only measured data is shown. Snapshots are stored per publishing job and the
latest snapshot per post is used so totals are never double counted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AnalyticsRecord, CandidateClip, ExportedVideo, PublishingJob, RenderJob, SourceVideo, SocialAccount
from . import publishing


def latest_records_subquery(workspace_id: str):
    latest = (
        select(
            AnalyticsRecord.publishing_job_id,
            func.max(AnalyticsRecord.captured_at).label("captured_at"),
        )
        .where(AnalyticsRecord.workspace_id == workspace_id)
        .group_by(AnalyticsRecord.publishing_job_id)
        .subquery()
    )
    return latest


def overview(db: Session, workspace_id: str) -> dict:
    latest = latest_records_subquery(workspace_id)
    rows = db.execute(
        select(
            PublishingJob.id,
            PublishingJob.platform,
            PublishingJob.title,
            PublishingJob.status,
            PublishingJob.external_url,
            PublishingJob.published_at,
            AnalyticsRecord.views,
            AnalyticsRecord.likes,
            AnalyticsRecord.comments,
            AnalyticsRecord.shares,
            AnalyticsRecord.watch_time_seconds,
            AnalyticsRecord.retention_pct,
            AnalyticsRecord.source,
            AnalyticsRecord.captured_at,
        )
        .join(AnalyticsRecord, AnalyticsRecord.publishing_job_id == PublishingJob.id)
        .join(
            latest,
            (AnalyticsRecord.publishing_job_id == latest.c.publishing_job_id)
            & (AnalyticsRecord.captured_at == latest.c.captured_at),
        )
        .where(PublishingJob.workspace_id == workspace_id)
    ).all()

    totals = {
        "videos": db.scalar(select(func.count()).select_from(SourceVideo).where(SourceVideo.workspace_id == workspace_id)) or 0,
        "clips": db.scalar(select(func.count()).select_from(CandidateClip).where(CandidateClip.workspace_id == workspace_id)) or 0,
        "approved_clips": db.scalar(
            select(func.count()).select_from(CandidateClip).where(
                CandidateClip.workspace_id == workspace_id, CandidateClip.status == "approved"
            )
        ) or 0,
        "renders": db.scalar(select(func.count()).select_from(RenderJob).where(RenderJob.workspace_id == workspace_id)) or 0,
        "exports": db.scalar(select(func.count()).select_from(ExportedVideo).where(ExportedVideo.workspace_id == workspace_id)) or 0,
        "published": db.scalar(
            select(func.count()).select_from(PublishingJob).where(
                PublishingJob.workspace_id == workspace_id, PublishingJob.status == "published"
            )
        ) or 0,
        "views": sum(int(row.views or 0) for row in rows),
        "likes": sum(int(row.likes or 0) for row in rows),
        "comments": sum(int(row.comments or 0) for row in rows),
        "shares": sum(int(row.shares or 0) for row in rows),
        "watch_time_seconds": round(sum(float(row.watch_time_seconds or 0) for row in rows), 1),
        "measured_posts": len(rows),
    }
    engagement_base = totals["views"]
    totals["engagement_rate"] = (
        round((totals["likes"] + totals["comments"] + totals["shares"]) / engagement_base * 100, 2)
        if engagement_base
        else 0.0
    )

    platforms: dict[str, dict] = {}
    for row in rows:
        bucket = platforms.setdefault(
            row.platform,
            {"platform": row.platform, "posts": 0, "views": 0, "likes": 0, "comments": 0, "shares": 0, "engagement_rate": 0.0},
        )
        bucket["posts"] += 1
        bucket["views"] += int(row.views or 0)
        bucket["likes"] += int(row.likes or 0)
        bucket["comments"] += int(row.comments or 0)
        bucket["shares"] += int(row.shares or 0)
    for bucket in platforms.values():
        bucket["engagement_rate"] = (
            round((bucket["likes"] + bucket["comments"] + bucket["shares"]) / bucket["views"] * 100, 2)
            if bucket["views"]
            else 0.0
        )

    series_map: dict[str, dict[str, float]] = {}
    for row in rows:
        captured = row.captured_at or datetime.now(timezone.utc)
        day = captured.strftime("%Y-%m-%d")
        entry = series_map.setdefault(day, {"date": day, "views": 0, "engagement": 0})
        entry["views"] += int(row.views or 0)
        entry["engagement"] += int(row.likes or 0) + int(row.comments or 0) + int(row.shares or 0)
    series = [series_map[key] for key in sorted(series_map.keys())][-30:]

    top_posts = [
        {
            "publishing_job_id": row.id,
            "title": row.title,
            "platform": row.platform,
            "views": int(row.views or 0),
            "likes": int(row.likes or 0),
            "comments": int(row.comments or 0),
            "shares": int(row.shares or 0),
            "retention_pct": round(float(row.retention_pct or 0), 1),
            "source": row.source,
            "external_url": row.external_url,
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }
        for row in sorted(rows, key=lambda r: int(r.views or 0), reverse=True)[:10]
    ]

    notes: list[str] = []
    if not rows:
        notes.append(
            "No measured analytics yet. Connect a platform and sync, or record numbers manually. "
            "FireClip never estimates views or engagement."
        )
    accounts = db.scalar(
        select(func.count()).select_from(SocialAccount).where(
            SocialAccount.workspace_id == workspace_id, SocialAccount.status == "connected"
        )
    ) or 0
    if accounts == 0:
        notes.append("No social accounts are connected, so platform API sync is unavailable.")
    notes.append("Retention and watch time are only shown when a platform returns them.")
    return {
        "totals": totals,
        "platform_breakdown": sorted(platforms.values(), key=lambda item: item["views"], reverse=True),
        "series": series,
        "top_posts": top_posts,
        "data_sources": sorted({row.source for row in rows}),
        "notes": notes,
    }


def sync(db: Session, workspace_id: str, user_id: str) -> dict:
    jobs = list(
        db.scalars(
            select(PublishingJob).where(
                PublishingJob.workspace_id == workspace_id,
                PublishingJob.status == "published",
                PublishingJob.external_post_id.is_not(None),
            )
        )
    )
    synced = 0
    skipped = 0
    messages: list[str] = []
    for job in jobs:
        account = db.get(SocialAccount, job.social_account_id)
        if not account:
            skipped += 1
            messages.append(f"{job.platform}: missing account for post {job.id}")
            continue
        try:
            metrics = publishing.fetch_metrics(db, account, job)
        except publishing.PublishError as exc:
            skipped += 1
            messages.append(f"{job.platform}: {exc}")
            continue
        if not metrics:
            skipped += 1
            messages.append(f"{job.platform}: no metrics endpoint available for this post")
            continue
        db.add(
            AnalyticsRecord(
                workspace_id=workspace_id,
                publishing_job_id=job.id,
                platform=job.platform,
                views=int(metrics.get("views", 0)),
                likes=int(metrics.get("likes", 0)),
                comments=int(metrics.get("comments", 0)),
                shares=int(metrics.get("shares", 0)),
                watch_time_seconds=float(metrics.get("watch_time_seconds", 0)),
                retention_pct=float(metrics.get("retention_pct", 0)),
                source="platform_api",
            )
        )
        synced += 1
    db.commit()
    if not jobs:
        messages.append("No published posts with external IDs to sync yet.")
    return {"synced": synced, "skipped": skipped, "messages": messages[:20]}


def add_manual(db: Session, workspace_id: str, payload) -> AnalyticsRecord:
    job = db.get(PublishingJob, payload.publishing_job_id)
    if not job or job.workspace_id != workspace_id:
        raise ValueError("Publishing job not found in this workspace")
    record = AnalyticsRecord(
        workspace_id=workspace_id,
        publishing_job_id=job.id,
        platform=job.platform,
        views=payload.views,
        likes=payload.likes,
        comments=payload.comments,
        shares=payload.shares,
        watch_time_seconds=payload.watch_time_seconds,
        retention_pct=payload.retention_pct,
        source="manual",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
