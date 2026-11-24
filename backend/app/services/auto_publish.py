"""Automatic publishing for campaign renders.

Only runs when a campaign explicitly opts in. Accounts must still be connected;
if no account is connected nothing is queued, and the UI reports the campaign
automation as incomplete instead of pretending a post happened.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Campaign, CandidateClip, ExportedVideo, PublishingJob, SocialAccount

from . import content


def next_slot(hour_utc: int, now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    slot = current.astimezone(timezone.utc).replace(
        hour=max(0, min(23, int(hour_utc))), minute=0, second=0, microsecond=0
    )
    if slot <= current:
        slot += timedelta(days=1)
    return slot


def _copy(clip: CandidateClip, video, platform: str, campaign: Campaign) -> tuple[str, str, str]:
    payload = dict(clip.content or {})
    if not payload.get("titles") or not payload.get("captions"):
        try:
            fallback = content.heuristic_content(clip, video)
            for key, value in fallback.items():
                if not payload.get(key):
                    payload[key] = value
        except Exception:
            pass
    titles = [str(item).strip() for item in payload.get("titles") or [] if str(item).strip()]
    title = (titles[0] if titles else clip.title or "New clip")[:240]
    captions = payload.get("captions") if isinstance(payload.get("captions"), dict) else {}
    caption = str(captions.get(platform) or clip.description or title).strip()
    brand = campaign.brand or {}
    cta = str(brand.get("cta") or "").strip()
    if cta and cta.lower() not in caption.lower():
        caption = f"{caption}\n\n{cta}".strip()
    brand_tags = brand.get("hashtags") or []
    if isinstance(brand_tags, str):
        brand_tags = brand_tags.replace(",", " ").split()
    tags = [str(item).strip() for item in brand_tags if str(item).strip()]
    ai_tags = payload.get("hashtags") or []
    if isinstance(ai_tags, str):
        ai_tags = ai_tags.replace(",", " ").split()
    for item in ai_tags:
        tag = str(item).strip()
        if tag and tag.lower() not in {existing.lower() for existing in tags}:
            tags.append(tag)
    hashtags = " ".join(tags[:20])
    return title, caption[:5000], hashtags[:2000]


def queue_for_export(
    db: Session,
    campaign: Campaign,
    export: ExportedVideo,
    clip: CandidateClip | None,
    video,
    created_by: str,
) -> list[tuple[str, str]]:
    """Create PublishingJob rows and return ``(pipeline_job_id, publish_job_id)`` pairs."""
    if not campaign.auto_publish or campaign.status != "active":
        return []
    score = float(clip.virality_score if clip else 0.0)
    if score < float(campaign.auto_publish_min_score or 0):
        return []
    account_ids = list(campaign.publish_account_ids or [])
    if not account_ids:
        return []
    accounts = list(
        db.scalars(
            select(SocialAccount).where(
                SocialAccount.workspace_id == export.workspace_id,
                SocialAccount.id.in_(account_ids),
                SocialAccount.status == "connected",
            )
        )
    )
    if not accounts:
        return []
    scheduled_for = None
    status = "queued"
    if campaign.publish_mode == "next_slot":
        scheduled_for = next_slot(campaign.publish_hour_utc)
        status = "scheduled"
    created: list[tuple[str, str]] = []
    for account in accounts:
        title, caption, hashtags = (
            _copy(clip, video, account.platform, campaign) if clip else (export.title, "", "")
        )
        job = PublishingJob(
            workspace_id=export.workspace_id,
            exported_video_id=export.id,
            social_account_id=account.id,
            platform=account.platform,
            title=title,
            caption=caption,
            hashtags=hashtags,
            privacy=campaign.publish_privacy or "public",
            scheduled_for=scheduled_for,
            status=status,
            created_by=created_by,
        )
        db.add(job)
        db.flush()
        if status == "queued":
            from ..jobs import create_pipeline_job

            pipeline = create_pipeline_job(
                db,
                workspace_id=export.workspace_id,
                video_id=None,
                kind="publishing",
                task_name="publish_video",
                payload={"publishing_job_id": job.id},
            )
            created.append((pipeline.id, job.id))
        else:
            created.append(("", job.id))
    return created
