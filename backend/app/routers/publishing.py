"""Social accounts, OAuth callbacks and the publishing queue."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from ..config import settings
from ..deps import RequestContext, get_context, record_audit
from ..jobs import create_pipeline_job, enqueue
from ..models import ExportedVideo, PublishingJob, SocialAccount
from ..schemas import ConnectStartOut, PublishRequest, PublishingJobOut, SocialAccountOut
from ..security import encrypt_secret, decrypt_secret
from ..services import publishing as pub_service
from .common import get_export

router = APIRouter(prefix="/api/publishing", tags=["publishing"])

PLATFORMS = {"youtube", "tiktok", "instagram", "facebook"}


def _account_out(account: SocialAccount) -> SocialAccountOut:
    return SocialAccountOut(
        id=account.id,
        platform=account.platform,
        account_name=account.account_name,
        external_id=account.external_id,
        status=account.status,
        scopes=account.scopes,
        token_expires_at=account.token_expires_at,
        last_error=account.last_error,
        created_at=account.created_at,
    )


def _job_out(ctx: RequestContext, job: PublishingJob) -> PublishingJobOut:
    account = ctx.db.get(SocialAccount, job.social_account_id)
    export = ctx.db.get(ExportedVideo, job.exported_video_id)
    return PublishingJobOut(
        id=job.id,
        exported_video_id=job.exported_video_id,
        social_account_id=job.social_account_id,
        platform=job.platform,
        title=job.title,
        caption=job.caption,
        hashtags=job.hashtags,
        privacy=job.privacy,
        scheduled_for=job.scheduled_for,
        status=job.status,
        external_post_id=job.external_post_id,
        external_url=job.external_url,
        attempts=job.attempts,
        error_message=job.error_message,
        published_at=job.published_at,
        created_at=job.created_at,
        account_name=account.account_name if account else "",
        video_title=export.title if export else "",
    )


@router.get("/accounts", response_model=list[SocialAccountOut])
def list_accounts(ctx: RequestContext = Depends(get_context)):
    rows = ctx.db.scalars(
        select(SocialAccount)
        .where(SocialAccount.workspace_id == ctx.workspace.id)
        .order_by(SocialAccount.created_at.desc())
    )
    return [_account_out(row) for row in rows]


@router.get("/connect/{platform}", response_model=ConnectStartOut)
def connect_start(platform: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    if platform not in PLATFORMS:
        raise HTTPException(status_code=404, detail="Unsupported platform")
    configured, url, message = pub_service.authorize_url(platform, ctx.workspace.id, ctx.user.id)
    return ConnectStartOut(platform=platform, configured=configured, authorize_url=url, message=message)


@router.get("/callback/{platform}")
def oauth_callback(
    platform: str,
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = None,
):
    frontend = settings.frontend_url.rstrip("/")
    if platform not in PLATFORMS:
        return RedirectResponse(f"{frontend}/accounts?status=error&message=Unsupported+platform")
    if error:
        return RedirectResponse(
            f"{frontend}/accounts?status=error&platform={platform}&message={error_description or error}"
        )
    if not code or not state:
        return RedirectResponse(f"{frontend}/accounts?status=error&platform={platform}&message=Missing+OAuth+code")

    from ..database import SessionLocal

    db = SessionLocal()
    try:
        state_payload = pub_service.decode_state(state, platform)
        workspace_id = state_payload.get("ws")
        user_id = state_payload.get("sub")
        if not workspace_id or not user_id:
            raise pub_service.PublishError("OAuth state is missing workspace information")
        data = pub_service.exchange_code(platform, code, state_payload)
        if not data.get("access_token"):
            raise pub_service.PublishError("The platform did not return an access token")
        account = db.scalar(
            select(SocialAccount).where(
                SocialAccount.workspace_id == workspace_id,
                SocialAccount.platform == platform,
                SocialAccount.external_id == data.get("external_id", ""),
            )
        )
        expires = (
            datetime.now(timezone.utc).replace(microsecond=0)
            + __import__("datetime").timedelta(seconds=int(data.get("expires_in") or 0))
            if data.get("expires_in")
            else None
        )
        if not account:
            account = SocialAccount(
                workspace_id=workspace_id,
                platform=platform,
                connected_by=user_id,
                external_id=data.get("external_id", ""),
            )
            db.add(account)
        account.account_name = data.get("account_name", "")[:160]
        account.access_token_encrypted = encrypt_secret(data.get("access_token", ""))
        if data.get("refresh_token"):
            account.refresh_token_encrypted = encrypt_secret(data["refresh_token"])
        account.token_expires_at = expires
        account.scopes = data.get("scopes", "")[:2000]
        account.status = "connected"
        account.last_error = None
        record_audit(db, "social.connect", workspace_id=workspace_id, user_id=user_id,
                     target_type="social_account", target_id=account.id, meta={"platform": platform})
        db.commit()
        return RedirectResponse(f"{frontend}/accounts?status=connected&platform={platform}")
    except Exception as exc:  # noqa: BLE001 - surfaced to the user in the redirect
        db.rollback()
        from urllib.parse import quote

        return RedirectResponse(
            f"{frontend}/accounts?status=error&platform={platform}&message={quote(str(exc)[:300])}"
        )
    finally:
        db.close()


@router.delete("/accounts/{account_id}", status_code=204)
def disconnect_account(account_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    account = ctx.db.get(SocialAccount, account_id)
    if not account or account.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Account not found")
    for job in ctx.db.scalars(
        select(PublishingJob).where(
            PublishingJob.social_account_id == account.id,
            PublishingJob.status.in_(["scheduled", "queued"]),
        )
    ):
        job.status = "cancelled"
        job.error_message = "Account disconnected"
    record_audit(ctx.db, "social.disconnect", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="social_account", target_id=account.id, meta={"platform": account.platform})
    ctx.db.delete(account)
    ctx.db.commit()


@router.get("/jobs", response_model=list[PublishingJobOut])
def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=300),
    ctx: RequestContext = Depends(get_context),
):
    query = select(PublishingJob).where(PublishingJob.workspace_id == ctx.workspace.id)
    if status_filter:
        query = query.where(PublishingJob.status == status_filter)
    jobs = ctx.db.scalars(query.order_by(PublishingJob.created_at.desc()).limit(limit))
    return [_job_out(ctx, job) for job in jobs]


@router.post("/jobs", response_model=PublishingJobOut, status_code=201)
def create_publishing_job(payload: PublishRequest, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    export = get_export(ctx, payload.exported_video_id)
    account = ctx.db.get(SocialAccount, payload.social_account_id)
    if not account or account.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Social account not found")
    if account.status != "connected" or not decrypt_secret(account.access_token_encrypted):
        raise HTTPException(status_code=400, detail="This account is not connected. Reconnect it first.")
    if not payload.caption.strip() and not payload.title.strip():
        raise HTTPException(status_code=400, detail="Add a caption or title before publishing")
    scheduled = payload.scheduled_for
    if scheduled and scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if payload.publish_now or not scheduled or scheduled <= now:
        status_value = "queued"
        scheduled = None
    else:
        status_value = "scheduled"
    job = PublishingJob(
        workspace_id=ctx.workspace.id,
        exported_video_id=export.id,
        social_account_id=account.id,
        platform=account.platform,
        title=payload.title.strip()[:240],
        caption=payload.caption.strip(),
        hashtags=payload.hashtags.strip(),
        privacy=payload.privacy,
        scheduled_for=scheduled,
        status=status_value,
        created_by=ctx.user.id,
    )
    ctx.db.add(job)
    record_audit(ctx.db, "publish.schedule", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="publishing_job", target_id=job.id, ip_address=ctx.ip_address,
                 meta={"platform": job.platform, "scheduled": bool(scheduled)})
    ctx.db.commit()
    if status_value == "queued":
        pipeline_job = create_pipeline_job(
            ctx.db,
            workspace_id=ctx.workspace.id,
            video_id=None,
            kind="publishing",
            task_name="publish_video",
            payload={"publishing_job_id": job.id},
        )
        enqueue(pipeline_job.id)
    return _job_out(ctx, job)


@router.post("/jobs/{job_id}/retry", response_model=PublishingJobOut, status_code=202)
def retry_publish(job_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    job = ctx.db.get(PublishingJob, job_id)
    if not job or job.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Publishing job not found")
    if job.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Only failed or cancelled jobs can be retried")
    job.status = "queued"
    job.error_message = None
    ctx.db.commit()
    pipeline_job = create_pipeline_job(
        ctx.db,
        workspace_id=ctx.workspace.id,
        video_id=None,
        kind="publishing",
        task_name="publish_video",
        payload={"publishing_job_id": job.id},
    )
    enqueue(pipeline_job.id)
    return _job_out(ctx, job)


@router.post("/jobs/{job_id}/cancel", response_model=PublishingJobOut)
def cancel_publish(job_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    job = ctx.db.get(PublishingJob, job_id)
    if not job or job.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Publishing job not found")
    if job.status not in {"scheduled", "queued"}:
        raise HTTPException(status_code=400, detail="Only scheduled or queued jobs can be cancelled")
    job.status = "cancelled"
    job.error_message = "Cancelled by user"
    ctx.db.commit()
    return _job_out(ctx, job)


@router.post("/run-due")
def run_due(ctx: RequestContext = Depends(get_context)):
    """Enqueue scheduled posts that are due (also runs on a background timer)."""
    ctx.require("editor")
    now = datetime.now(timezone.utc)
    due = list(
        ctx.db.scalars(
            select(PublishingJob).where(
                PublishingJob.workspace_id == ctx.workspace.id,
                PublishingJob.status == "scheduled",
                PublishingJob.scheduled_for <= now,
            )
        )
    )
    count = 0
    for job in due:
        job.status = "queued"
        pipeline_job = create_pipeline_job(
            ctx.db,
            workspace_id=ctx.workspace.id,
            video_id=None,
            kind="publishing",
            task_name="publish_video",
            payload={"publishing_job_id": job.id},
        )
        enqueue(pipeline_job.id)
        count += 1
    ctx.db.commit()
    return {"enqueued": count}
