"""Video ingestion, library, transcripts and clip discovery routes."""
from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, or_, select

from ..config import settings
from ..deps import RequestContext, get_context, notify, rate_limit, record_audit
from ..jobs import cancel_job, create_pipeline_job, enqueue
from ..models import (
    Campaign,
    CandidateClip,
    EditingProject,
    ExportedVideo,
    PipelineJob,
    Project,
    RenderJob,
    SourceVideo,
    Speaker,
    Transcript,
    TranscriptSegment,
)
from ..schemas import (
    AnalyzeRequest,
    ClipCreate,
    ClipOut,
    ClipUpdate,
    ImportUrlRequest,
    SegmentUpdate,
    SpeakerUpdate,
    TranscribeRequest,
    TranscriptOut,
    VideoDetail,
    VideoOut,
    VideoUpdate,
)
from ..services import billing, sources as source_service, storage_guard
from ..storage import build_key, get_storage, safe_filename
from .common import clip_out, get_clip, get_video, video_detail, video_out
from .media_utils import serve_key

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.get("", response_model=list[VideoOut])
def list_videos(
    status_filter: str | None = Query(default=None, alias="status"),
    project_id: str | None = None,
    campaign_id: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = Depends(get_context),
):
    query = select(SourceVideo).where(SourceVideo.workspace_id == ctx.workspace.id)
    if status_filter:
        query = query.where(SourceVideo.status == status_filter)
    if project_id:
        query = query.where(SourceVideo.project_id == project_id)
    if campaign_id:
        query = query.where(SourceVideo.campaign_id == campaign_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(SourceVideo.title.ilike(term), SourceVideo.description.ilike(term)))
    rows = ctx.db.scalars(
        query.order_by(SourceVideo.created_at.desc()).limit(limit).offset(offset)
    )
    return [video_out(video) for video in rows]


@router.post("/upload", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    campaign_id: str | None = Form(default=None),
    title: str | None = Form(default=None),
    auto_pipeline: bool = Form(default=True),
    ctx: RequestContext = Depends(get_context),
    _limit=Depends(rate_limit("upload", 20)),
):
    ctx.require("editor")
    try:
        storage_guard.check_capacity(ctx.db, ctx.workspace.id, 0)
    except storage_guard.StorageGuardError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    original = safe_filename(file.filename or "upload.mp4")
    try:
        source_service.assert_media_extension(original)
    except source_service.SourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    max_bytes = settings.max_upload_mb * 1024 * 1024
    temp_path = settings.data_dir / "tmp" / f"upload-{uuid.uuid4().hex}-{original}"
    digest = hashlib.sha256()
    size = 0
    try:
        with open(temp_path, "wb") as handle:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {settings.max_upload_mb}MB upload limit",
                    )
                digest.update(chunk)
                handle.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    if size == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    checksum = digest.hexdigest()
    try:
        storage_guard.check_capacity(ctx.db, ctx.workspace.id, size)
    except storage_guard.StorageGuardError as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    duplicate = ctx.db.scalar(
        select(SourceVideo).where(
            SourceVideo.workspace_id == ctx.workspace.id, SourceVideo.checksum == checksum
        )
    )
    if duplicate:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail=f"This file is already in your library as “{duplicate.title}”.",
        )
    if project_id:
        project = ctx.db.get(Project, project_id)
        if not project or project.workspace_id != ctx.workspace.id:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Project not found")
    if campaign_id:
        campaign = ctx.db.get(Campaign, campaign_id)
        if not campaign or campaign.workspace_id != ctx.workspace.id:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Campaign not found")

    video_id = uuid.uuid4().hex
    suffix = Path(original).suffix.lower()
    storage = get_storage()
    key = build_key("uploads", ctx.workspace.id, f"{video_id}{suffix}")
    try:
        storage.put_file(temp_path, key, file.content_type or source_service.guess_mime(Path(original)))
    finally:
        temp_path.unlink(missing_ok=True)

    video = SourceVideo(
        id=video_id,
        workspace_id=ctx.workspace.id,
        project_id=project_id,
        campaign_id=campaign_id,
        created_by=ctx.user.id,
        title=(title or Path(original).stem)[:300],
        source_type="upload",
        original_filename=original,
        storage_key=key,
        mime_type=file.content_type or source_service.guess_mime(Path(original)),
        size_bytes=size,
        checksum=checksum,
        status="uploaded",
        progress=0,
    )
    ctx.db.add(video)
    record_audit(ctx.db, "video.upload", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="video", target_id=video.id, ip_address=ctx.ip_address,
                 meta={"filename": original, "size": size})
    ctx.db.commit()
    job = create_pipeline_job(
        ctx.db,
        workspace_id=ctx.workspace.id,
        video_id=video.id,
        kind="ingestion",
        task_name="ingest_video",
        payload={"video_id": video.id, "auto_pipeline": auto_pipeline},
    )
    enqueue(job.id)
    return video_out(video)


@router.post("/import", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
def import_video(
    payload: ImportUrlRequest,
    ctx: RequestContext = Depends(get_context),
    _limit=Depends(rate_limit("import", 15)),
):
    ctx.require("editor")
    try:
        url = source_service.validate_url(payload.url)
        info = source_service.fetch_source_info(url)
    except source_service.SourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if info.duration and info.duration > settings.max_import_minutes * 60:
        raise HTTPException(
            status_code=400,
            detail=f"Video exceeds the {settings.max_import_minutes} minute import limit",
        )
    if payload.campaign_id:
        campaign = ctx.db.get(Campaign, payload.campaign_id)
        if not campaign or campaign.workspace_id != ctx.workspace.id:
            raise HTTPException(status_code=400, detail="Campaign not found")
    video = SourceVideo(
        workspace_id=ctx.workspace.id,
        project_id=payload.project_id,
        campaign_id=payload.campaign_id,
        created_by=ctx.user.id,
        title=(payload.title or info.title or "Imported video")[:300],
        description=info.description[:4000],
        source_type=info.platform,
        source_url=url,
        mime_type="video/mp4",
        status="downloading",
        progress=0,
        metadata_extra={"uploader": info.uploader, "platform": info.platform},
    )
    ctx.db.add(video)
    record_audit(ctx.db, "video.import", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="video", target_id=video.id, ip_address=ctx.ip_address,
                 meta={"platform": info.platform})
    ctx.db.commit()
    job = create_pipeline_job(
        ctx.db,
        workspace_id=ctx.workspace.id,
        video_id=video.id,
        kind="ingestion",
        task_name="ingest_video",
        payload={"video_id": video.id, "auto_pipeline": True},
    )
    enqueue(job.id)
    return video_out(video)


@router.get("/{video_id}", response_model=VideoDetail)
def get_video_detail(video_id: str, ctx: RequestContext = Depends(get_context)):
    video = get_video(ctx, video_id)
    return video_detail(ctx.db, video)


@router.patch("/{video_id}", response_model=VideoOut)
def update_video(video_id: str, payload: VideoUpdate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    video = get_video(ctx, video_id)
    if payload.title is not None:
        video.title = payload.title.strip()
    if payload.description is not None:
        video.description = payload.description.strip()
    if payload.project_id is not None:
        video.project_id = payload.project_id or None
    if "campaign_id" in payload.model_fields_set:
        if payload.campaign_id:
            campaign = ctx.db.get(Campaign, payload.campaign_id)
            if not campaign or campaign.workspace_id != ctx.workspace.id:
                raise HTTPException(status_code=400, detail="Campaign not found")
            video.campaign_id = campaign.id
        else:
            video.campaign_id = None
    ctx.db.commit()
    return video_out(video)


@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    video = get_video(ctx, video_id)
    storage = get_storage()
    keys = [video.storage_key, video.thumbnail_key]
    # Remove exported media belonging to this video's edit projects before the cascade.
    project_ids = list(
        ctx.db.scalars(select(EditingProject.id).where(EditingProject.video_id == video.id))
    )
    if project_ids:
        render_ids = list(
            ctx.db.scalars(select(RenderJob.id).where(RenderJob.editing_project_id.in_(project_ids)))
        )
        if render_ids:
            for export in ctx.db.scalars(
                select(ExportedVideo).where(ExportedVideo.render_job_id.in_(render_ids))
            ):
                keys.extend([export.storage_key, export.thumbnail_key])
    for job in ctx.db.scalars(
        select(PipelineJob).where(PipelineJob.video_id == video.id, PipelineJob.status.in_(["queued", "running"]))
    ):
        cancel_job(ctx.db, job.id, ctx.workspace.id)
    record_audit(ctx.db, "video.delete", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="video", target_id=video.id, ip_address=ctx.ip_address,
                 meta={"title": video.title})
    ctx.db.delete(video)
    ctx.db.commit()
    for key in keys:
        if key:
            try:
                storage.delete(key)
            except Exception:
                pass


@router.post("/{video_id}/retry", response_model=VideoOut)
def retry_video(video_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    video = get_video(ctx, video_id)
    if video.status not in {"error", "uploaded"}:
        raise HTTPException(status_code=400, detail="Only failed or unprocessed videos can be retried")
    video.status = "uploaded"
    video.error_message = None
    video.progress = 0
    ctx.db.commit()
    job = create_pipeline_job(
        ctx.db,
        workspace_id=ctx.workspace.id,
        video_id=video.id,
        kind="ingestion",
        task_name="ingest_video",
        payload={"video_id": video.id, "auto_pipeline": True},
    )
    enqueue(job.id)
    return video_out(video)


@router.get("/{video_id}/stream")
def stream_video(video_id: str, request: Request, ctx: RequestContext = Depends(get_context)):
    video = get_video(ctx, video_id)
    if not video.storage_key:
        raise HTTPException(status_code=404, detail="Video file is not available yet")
    return serve_key(request, video.storage_key)


@router.get("/{video_id}/thumbnail")
def video_thumbnail(video_id: str, request: Request, ctx: RequestContext = Depends(get_context)):
    video = get_video(ctx, video_id)
    if not video.thumbnail_key:
        raise HTTPException(status_code=404, detail="No thumbnail yet")
    return serve_key(request, video.thumbnail_key)


@router.get("/{video_id}/jobs")
def video_jobs(video_id: str, ctx: RequestContext = Depends(get_context)):
    get_video(ctx, video_id)
    rows = ctx.db.scalars(
        select(PipelineJob).where(PipelineJob.video_id == video_id).order_by(PipelineJob.created_at.desc()).limit(20)
    )
    return [
        {
            "id": job.id,
            "kind": job.kind,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "error_message": job.error_message,
            "attempts": job.attempts,
            "created_at": job.created_at,
            "finished_at": job.finished_at,
        }
        for job in rows
    ]


@router.post("/{video_id}/transcribe", status_code=202)
def transcribe(
    video_id: str,
    payload: TranscribeRequest,
    ctx: RequestContext = Depends(get_context),
):
    ctx.require("editor")
    video = get_video(ctx, video_id)
    if not video.storage_key:
        raise HTTPException(status_code=400, detail="Wait for the upload to finish processing")
    if not video.has_audio and video.status == "ready":
        raise HTTPException(status_code=400, detail="This video has no audio track")
    existing = ctx.db.scalar(
        select(PipelineJob).where(
            PipelineJob.video_id == video.id,
            PipelineJob.task_name == "transcribe_video",
            PipelineJob.status.in_(["queued", "running"]),
        )
    )
    if existing:
        return {"job_id": existing.id, "status": existing.status}
    job = create_pipeline_job(
        ctx.db,
        workspace_id=ctx.workspace.id,
        video_id=video.id,
        kind="transcription",
        task_name="transcribe_video",
        payload={
            "video_id": video.id,
            "engine": payload.engine,
            "language": payload.language,
            "force": payload.force,
            "auto_analyze": False,
        },
    )
    enqueue(job.id)
    return {"job_id": job.id, "status": job.status}


@router.get("/{video_id}/transcript", response_model=TranscriptOut)
def get_transcript(video_id: str, ctx: RequestContext = Depends(get_context)):
    video = get_video(ctx, video_id)
    transcript = ctx.db.scalar(
        select(Transcript)
        .where(Transcript.video_id == video.id)
        .order_by(Transcript.created_at.desc())
    )
    if not transcript:
        raise HTTPException(status_code=404, detail="No transcript yet")
    segments = list(
        ctx.db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.start_ms)
        )
    )
    speakers = list(ctx.db.scalars(select(Speaker).where(Speaker.video_id == video.id)))
    return {
        "id": transcript.id,
        "video_id": transcript.video_id,
        "language": transcript.language,
        "engine": transcript.engine,
        "model": transcript.model,
        "status": transcript.status,
        "full_text": transcript.full_text,
        "word_count": transcript.word_count,
        "error_message": transcript.error_message,
        "segments": segments,
        "speakers": speakers,
    }


@router.patch("/{video_id}/transcript/segments/{segment_id}")
def update_segment(
    video_id: str,
    segment_id: str,
    payload: SegmentUpdate,
    ctx: RequestContext = Depends(get_context),
):
    ctx.require("editor")
    video = get_video(ctx, video_id)
    segment = ctx.db.get(TranscriptSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    transcript = ctx.db.get(Transcript, segment.transcript_id)
    if not transcript or transcript.video_id != video.id:
        raise HTTPException(status_code=404, detail="Segment not found")
    segment.text = payload.text
    segment.words = []  # edited text cannot keep stale word timings
    if payload.speaker_id is not None:
        speaker = ctx.db.get(Speaker, payload.speaker_id)
        if speaker and speaker.video_id == video.id:
            segment.speaker_id = speaker.id
    if payload.start_ms is not None:
        segment.start_ms = payload.start_ms
    if payload.end_ms is not None:
        segment.end_ms = max(payload.start_ms or segment.start_ms, payload.end_ms)
    ctx.db.flush()
    transcript.full_text = " ".join(
        row.text for row in ctx.db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.start_ms)
        )
    )
    ctx.db.commit()
    return {
        "id": segment.id, "start_ms": segment.start_ms, "end_ms": segment.end_ms,
        "text": segment.text, "speaker_id": segment.speaker_id,
        "confidence": segment.confidence, "words": segment.words,
    }


@router.patch("/{video_id}/transcript/speakers/{speaker_id}")
def update_speaker(
    video_id: str,
    speaker_id: str,
    payload: SpeakerUpdate,
    ctx: RequestContext = Depends(get_context),
):
    ctx.require("editor")
    video = get_video(ctx, video_id)
    speaker = ctx.db.get(Speaker, speaker_id)
    if not speaker or speaker.video_id != video.id:
        raise HTTPException(status_code=404, detail="Speaker not found")
    speaker.display_name = payload.display_name.strip()
    ctx.db.commit()
    return {"id": speaker.id, "label": speaker.label, "display_name": speaker.display_name}


@router.post("/{video_id}/analyze", status_code=202)
def analyze(
    video_id: str,
    payload: AnalyzeRequest,
    ctx: RequestContext = Depends(get_context),
    _limit=Depends(rate_limit("analyze", 30)),
):
    ctx.require("editor")
    video = get_video(ctx, video_id)
    transcript = ctx.db.scalar(
        select(Transcript).where(Transcript.video_id == video.id, Transcript.status == "completed")
    )
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcribe this video before running AI analysis")
    existing = ctx.db.scalar(
        select(PipelineJob).where(
            PipelineJob.video_id == video.id,
            PipelineJob.task_name == "analyze_video",
            PipelineJob.status.in_(["queued", "running"]),
        )
    )
    if existing:
        return {"job_id": existing.id, "status": existing.status}
    job = create_pipeline_job(
        ctx.db,
        workspace_id=ctx.workspace.id,
        video_id=video.id,
        kind="analysis",
        task_name="analyze_video",
        payload={
            "video_id": video.id,
            "provider": payload.provider,
            "target_duration_ms": payload.target_duration_ms,
            "clip_count": payload.clip_count,
            "replace_existing": payload.replace_existing,
            "ignore_static": payload.ignore_static,
        },
    )
    enqueue(job.id)
    return {"job_id": job.id, "status": job.status}


@router.get("/{video_id}/clips", response_model=list[ClipOut])
def list_video_clips(video_id: str, ctx: RequestContext = Depends(get_context)):
    video = get_video(ctx, video_id)
    clips = ctx.db.scalars(
        select(CandidateClip)
        .where(CandidateClip.video_id == video.id)
        .order_by(CandidateClip.virality_score.desc())
    )
    return [clip_out(clip, video) for clip in clips]


@router.post("/{video_id}/clips", response_model=ClipOut, status_code=201)
def create_manual_clip(video_id: str, payload: ClipCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    video = get_video(ctx, video_id)
    if payload.end_ms <= payload.start_ms:
        raise HTTPException(status_code=400, detail="End must be after start")
    if video.duration_seconds and payload.end_ms > int(video.duration_seconds * 1000) + 500:
        raise HTTPException(status_code=400, detail="Clip range is outside the video")
    if payload.end_ms - payload.start_ms < 1000:
        raise HTTPException(status_code=400, detail="Clip must be at least 1 second long")
    if billing.clips_used_this_month(ctx.db, ctx.workspace.id) >= ctx.workspace.monthly_clip_limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Monthly clip limit reached ({ctx.workspace.monthly_clip_limit}). "
                "Upgrade the workspace plan or wait until next month."
            ),
        )
    transcript_text = ""
    transcript = ctx.db.scalar(
        select(Transcript).where(Transcript.video_id == video.id, Transcript.status == "completed")
    )
    if transcript:
        transcript_text = " ".join(
            row.text
            for row in ctx.db.scalars(
                select(TranscriptSegment).where(
                    TranscriptSegment.transcript_id == transcript.id,
                    TranscriptSegment.end_ms > payload.start_ms,
                    TranscriptSegment.start_ms < payload.end_ms,
                )
            )
        )
    clip = CandidateClip(
        workspace_id=ctx.workspace.id,
        video_id=video.id,
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
        duration_ms=payload.end_ms - payload.start_ms,
        title=payload.title,
        description=transcript_text[:600],
        hook=transcript_text[:160],
        transcript_text=transcript_text,
        explanation="Manually selected by a team member.",
        virality_score=0,
        engagement_potential=0,
        signals={},
        aspect_ratio=payload.aspect_ratio,
        source="manual",
        status="suggested",
    )
    ctx.db.add(clip)
    record_audit(ctx.db, "clip.create_manual", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="clip", target_id=clip.id, ip_address=ctx.ip_address)
    ctx.db.commit()
    return clip_out(clip, video)
