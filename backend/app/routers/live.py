"""Live stream monitoring / recording.

Recording uses yt-dlp against public live URLs. Platform terms, access controls
and copyright are respected: nothing bypasses authentication or DRM. Stop
cancels the recording job, which terminates the download process.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..deps import RequestContext, get_context, record_audit
from ..jobs import cancel_job, create_pipeline_job, enqueue
from ..models import Campaign, LiveStream, PipelineJob, SourceVideo
from ..schemas import LiveStreamCreate, LiveStreamUpdate
from ..services import sources

router = APIRouter(prefix="/api/live-streams", tags=["live"])

SUPPORTED = {"youtube", "twitch", "kick"}


def _out(stream: LiveStream) -> dict:
    return {
        "id": stream.id,
        "platform": stream.platform,
        "url": stream.url,
        "title": stream.title,
        "status": stream.status,
        "campaign_id": stream.campaign_id,
        "auto_record": stream.auto_record,
        "auto_clip": stream.auto_clip,
        "last_checked_at": stream.last_checked_at,
        "recording_video_id": stream.recording_video_id,
        "started_at": stream.started_at,
        "ended_at": stream.ended_at,
        "error_message": stream.error_message,
        "created_at": stream.created_at,
    }


@router.get("")
def list_streams(ctx: RequestContext = Depends(get_context)):
    rows = ctx.db.scalars(
        select(LiveStream).where(LiveStream.workspace_id == ctx.workspace.id).order_by(LiveStream.created_at.desc())
    )
    return [_out(row) for row in rows]


@router.post("", status_code=201)
def add_stream(payload: LiveStreamCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    try:
        url = sources.validate_url(payload.url)
    except sources.SourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    platform = sources.detect_platform(url)
    if platform not in SUPPORTED:
        raise HTTPException(status_code=400, detail="Use a YouTube, Twitch or Kick live URL")
    if not sources.ytdlp_available():
        raise HTTPException(
            status_code=503,
            detail="Live recording requires yt-dlp on the server. Install it and restart the API.",
        )
    campaign_id = payload.campaign_id or None
    if campaign_id:
        campaign = ctx.db.get(Campaign, campaign_id)
        if not campaign or campaign.workspace_id != ctx.workspace.id:
            raise HTTPException(status_code=400, detail="Campaign not found")
    stream = LiveStream(
        workspace_id=ctx.workspace.id,
        created_by=ctx.user.id,
        platform=platform,
        url=url,
        title=(payload.title or f"{platform.title()} live stream")[:200],
        status="monitoring",
        campaign_id=campaign_id,
        auto_record=payload.auto_record,
        auto_clip=payload.auto_clip,
    )
    ctx.db.add(stream)
    ctx.db.flush()
    record_audit(ctx.db, "live.add", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="live_stream", target_id=stream.id, ip_address=ctx.ip_address)
    ctx.db.commit()
    return _out(stream)


@router.post("/{stream_id}/start")
def start_recording(stream_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    stream = ctx.db.get(LiveStream, stream_id)
    if not stream or stream.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Live stream not found")
    if stream.status == "recording":
        raise HTTPException(status_code=409, detail="This stream is already recording")
    if not sources.ytdlp_available():
        raise HTTPException(status_code=503, detail="yt-dlp is required to record live streams")
    video = SourceVideo(
        workspace_id=ctx.workspace.id,
        campaign_id=stream.campaign_id,
        created_by=ctx.user.id,
        title=stream.title or "Live recording",
        source_type=stream.platform,
        source_url=stream.url,
        mime_type="video/mp4",
        status="downloading",
    )
    ctx.db.add(video)
    ctx.db.flush()
    stream.status = "recording"
    stream.started_at = datetime.now(timezone.utc)
    stream.recording_video_id = video.id
    stream.error_message = None
    ctx.db.commit()
    job = create_pipeline_job(
        ctx.db,
        workspace_id=ctx.workspace.id,
        video_id=video.id,
        kind="live",
        task_name="record_live",
        payload={
            "video_id": video.id,
            "live_stream_id": stream.id,
            "auto_clip": stream.auto_clip,
        },
    )
    enqueue(job.id)
    return {"stream": _out(stream), "video_id": video.id, "job_id": job.id}


@router.patch("/{stream_id}")
def update_stream(
    stream_id: str, payload: LiveStreamUpdate, ctx: RequestContext = Depends(get_context)
):
    ctx.require("editor")
    stream = ctx.db.get(LiveStream, stream_id)
    if not stream or stream.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Live stream not found")
    if payload.title is not None:
        stream.title = payload.title.strip()
    if "campaign_id" in payload.model_fields_set:
        if payload.campaign_id:
            campaign = ctx.db.get(Campaign, payload.campaign_id)
            if not campaign or campaign.workspace_id != ctx.workspace.id:
                raise HTTPException(status_code=400, detail="Campaign not found")
            stream.campaign_id = campaign.id
        else:
            stream.campaign_id = None
    if payload.auto_record is not None:
        if payload.auto_record and not sources.ytdlp_available():
            raise HTTPException(status_code=503, detail="yt-dlp is required for automatic recording")
        stream.auto_record = payload.auto_record
    if payload.auto_clip is not None:
        stream.auto_clip = payload.auto_clip
    ctx.db.commit()
    return _out(stream)


@router.post("/{stream_id}/stop")
def stop_recording(stream_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    stream = ctx.db.get(LiveStream, stream_id)
    if not stream or stream.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Live stream not found")
    if stream.recording_video_id:
        for job in ctx.db.scalars(
            select(PipelineJob).where(
                PipelineJob.video_id == stream.recording_video_id,
                PipelineJob.status.in_(["queued", "running"]),
            )
        ):
            cancel_job(ctx.db, job.id, ctx.workspace.id)
    stream.status = "recorded" if stream.recording_video_id else "stopped"
    stream.ended_at = datetime.now(timezone.utc)
    ctx.db.commit()
    return _out(stream)


@router.delete("/{stream_id}", status_code=204)
def delete_stream(stream_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    stream = ctx.db.get(LiveStream, stream_id)
    if not stream or stream.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Live stream not found")
    if stream.recording_video_id:
        for job in ctx.db.scalars(
            select(PipelineJob).where(
                PipelineJob.video_id == stream.recording_video_id,
                PipelineJob.status.in_(["queued", "running"]),
            )
        ):
            cancel_job(ctx.db, job.id, ctx.workspace.id)
    ctx.db.delete(stream)
    ctx.db.commit()
