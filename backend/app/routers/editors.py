"""Editing projects, caption styles, subject framing and render enqueueing."""
from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from ..config import settings
from ..deps import RequestContext, get_context, record_audit
from ..jobs import create_pipeline_job, enqueue
from ..models import (
    CandidateClip,
    CaptionStyle,
    EditingProject,
    RenderJob,
    SourceVideo,
    Transcript,
    TranscriptSegment,
    UsageRecord,
)
from ..schemas import (
    CaptionStyleCreate,
    CaptionTranslationRequest,
    CaptionStyleOut,
    EditorCreate,
    EditorDetail,
    EditorOut,
    EditorUpdate,
    RenderOut,
    RenderRequest,
    TranscriptOut,
)
from ..services import ai as ai_service
from ..services import facetrack, translation
from ..services.render import PRESETS, RenderError
from ..services.transcription import SegmentData
from ..storage import get_storage
from .common import get_editor, get_video, render_out

router = APIRouter(prefix="/api", tags=["editors"])

ASPECT_SIZES = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080), "4:5": (1080, 1350)}


@router.get("/editors", response_model=list[EditorOut])
def list_editors(limit: int = Query(default=50, ge=1, le=200), ctx: RequestContext = Depends(get_context)):
    rows = ctx.db.scalars(
        select(EditingProject)
        .where(EditingProject.workspace_id == ctx.workspace.id)
        .order_by(EditingProject.updated_at.desc())
        .limit(limit)
    )
    return list(rows)


@router.post("/editors", response_model=EditorOut, status_code=201)
def create_editor(payload: EditorCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    if payload.clip_id:
        clip = ctx.db.get(CandidateClip, payload.clip_id)
        if not clip or clip.workspace_id != ctx.workspace.id:
            raise HTTPException(status_code=404, detail="Clip not found")
        existing = ctx.db.scalar(
            select(EditingProject).where(EditingProject.clip_id == clip.id).order_by(EditingProject.created_at.desc())
        )
        if existing:
            return existing
        video_id = clip.video_id
        trim_start, trim_end = clip.start_ms, clip.end_ms
        aspect = payload.aspect_ratio if payload.aspect_ratio != "9:16" else clip.aspect_ratio
        name = payload.name or clip.title
    else:
        if not payload.video_id:
            raise HTTPException(status_code=400, detail="Provide a clip_id or video_id")
        video = get_video(ctx, payload.video_id)
        video_id = video.id
        trim_start = 0
        trim_end = int((video.duration_seconds or 60) * 1000)
        aspect = payload.aspect_ratio
        name = payload.name or f"{video.title} clip"
    if trim_end <= trim_start:
        raise HTTPException(status_code=400, detail="Invalid clip range")
    width, height = ASPECT_SIZES.get(aspect, (1080, 1920))
    project = EditingProject(
        workspace_id=ctx.workspace.id,
        video_id=video_id,
        clip_id=payload.clip_id,
        created_by=ctx.user.id,
        name=name[:160],
        aspect_ratio=aspect,
        width=width,
        height=height,
        trim_start_ms=trim_start,
        trim_end_ms=trim_end,
        audio={"volume": 1.0, "muted": False},
    )
    ctx.db.add(project)
    record_audit(ctx.db, "editor.create", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="editing_project", target_id=project.id, ip_address=ctx.ip_address)
    ctx.db.commit()
    return project


@router.get("/editors/{project_id}", response_model=EditorDetail)
def get_editor_detail(project_id: str, ctx: RequestContext = Depends(get_context)):
    project = get_editor(ctx, project_id)
    video = ctx.db.get(SourceVideo, project.video_id)
    transcript = ctx.db.scalar(
        select(Transcript)
        .where(Transcript.video_id == project.video_id, Transcript.status == "completed")
        .order_by(Transcript.created_at.desc())
    )
    transcript_payload = None
    if transcript:
        segments = list(
            ctx.db.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.start_ms)
            )
        )
        from ..models import Speaker

        transcript_payload = {
            "id": transcript.id,
            "video_id": transcript.video_id,
            "language": transcript.language,
            "engine": transcript.engine,
            "model": transcript.model,
            "status": transcript.status,
            "full_text": transcript.full_text,
            "word_count": transcript.word_count,
            "segments": segments,
            "speakers": list(ctx.db.scalars(select(Speaker).where(Speaker.video_id == video.id))) if video else [],
        }
    latest = ctx.db.scalar(
        select(RenderJob).where(RenderJob.editing_project_id == project.id).order_by(RenderJob.created_at.desc())
    )
    return {
        **EditorOut.model_validate(project).model_dump(),
        "video_title": video.title if video else "",
        "video_duration_seconds": video.duration_seconds if video else 0,
        "video_width": video.width if video else 0,
        "video_height": video.height if video else 0,
        "transcript": transcript_payload,
        "latest_render": render_out(latest, project=project, video=video) if latest else None,
    }


@router.patch("/editors/{project_id}", response_model=EditorOut)
def update_editor(project_id: str, payload: EditorUpdate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    project = get_editor(ctx, project_id)
    video = ctx.db.get(SourceVideo, project.video_id)
    data = payload.model_dump(exclude_unset=True)
    if "aspect_ratio" in data and data["aspect_ratio"] and data["aspect_ratio"] != "custom":
        width, height = ASPECT_SIZES.get(data["aspect_ratio"], (1080, 1920))
        project.width, project.height = width, height
    for field in (
        "name", "aspect_ratio", "width", "height", "trim_start_ms", "trim_end_ms",
        "focus_x", "focus_y", "caption_style_id", "captions_enabled",
        "caption_overrides", "caption_translation", "layout", "overlays", "music", "audio", "operations",
    ):
        if field in data and data[field] is not None:
            setattr(project, field, data[field])
    if project.trim_end_ms <= project.trim_start_ms:
        raise HTTPException(status_code=400, detail="Clip end must be after its start")
    if video and video.duration_seconds:
        max_ms = int(video.duration_seconds * 1000)
        project.trim_start_ms = min(project.trim_start_ms, max(0, max_ms - 1000))
        project.trim_end_ms = min(project.trim_end_ms, max_ms)
    if project.trim_end_ms <= project.trim_start_ms:
        raise HTTPException(status_code=400, detail="Clip is outside the video duration")
    if len(project.operations or []) > 100:
        project.operations = (project.operations or [])[-100:]
    if payload.overlays is not None and len(payload.overlays) > 40:
        raise HTTPException(status_code=400, detail="Too many overlays")
    if payload.layout is not None:
        mode = str(payload.layout.get("mode", "fill"))
        if mode not in {"fill", "fit", "facecam"}:
            raise HTTPException(status_code=422, detail="Layout mode must be fill, fit or facecam")
        position = payload.layout.get("position")
        allowed_positions = {
            "bottom_right",
            "bottom_left",
            "bottom_center",
            "bottom_half",
            "top_right",
            "top_left",
            "manual",
        }
        if position is not None and position not in allowed_positions:
            raise HTTPException(status_code=422, detail="Unknown face cam position")
        for key in ("camera_x", "camera_y", "camera_w", "camera_h", "x", "y"):
            value = payload.layout.get(key)
            if value is not None and not 0 <= float(value) <= 1:
                raise HTTPException(status_code=422, detail=f"Layout field {key} must be between 0 and 1")
        size = payload.layout.get("size")
        if size is not None and not 0.1 <= float(size) <= 1:
            raise HTTPException(status_code=422, detail="Layout size must be between 0.1 and 1")
    project.status = "draft"
    ctx.db.commit()
    ctx.db.refresh(project)
    return project


@router.delete("/editors/{project_id}", status_code=204)
def delete_editor(project_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    project = get_editor(ctx, project_id)
    storage = get_storage()
    for render in ctx.db.scalars(select(RenderJob).where(RenderJob.editing_project_id == project.id)):
        if render.output_key:
            try:
                storage.delete(render.output_key)
                storage.delete(render.thumbnail_key or "")
            except Exception:
                pass
    ctx.db.delete(project)
    ctx.db.commit()


@router.post("/editors/{project_id}/auto-focus")
def auto_focus(project_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    project = get_editor(ctx, project_id)
    video = ctx.db.get(SourceVideo, project.video_id)
    if not video or not video.storage_key:
        raise HTTPException(status_code=400, detail="Video file is unavailable")
    if not facetrack.available():
        raise HTTPException(
            status_code=503,
            detail="Face detection is not installed on this server. Install opencv-python-headless or "
                   "adjust the framing manually.",
        )
    storage = get_storage()
    try:
        with storage.temp_copy(video.storage_key) as path:
            result = facetrack.detect_focus(
                path,
                clip_start_ms=project.trim_start_ms,
                clip_end_ms=project.trim_end_ms,
                target_width=project.width,
                target_height=project.height,
            )
    except facetrack.FaceTrackingUnavailable as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    project.focus_x = result.focus_x
    project.focus_y = result.focus_y
    layout = dict(project.layout or {})
    layout.update(
        {
            "camera_x": result.camera_x,
            "camera_y": result.camera_y,
            "camera_w": result.camera_w,
            "camera_h": result.camera_h,
        }
    )
    project.layout = layout
    ctx.db.commit()
    return {
        "focus_x": result.focus_x,
        "focus_y": result.focus_y,
        "camera_x": result.camera_x,
        "camera_y": result.camera_y,
        "camera_w": result.camera_w,
        "camera_h": result.camera_h,
        "faces_detected": result.faces_detected,
        "samples": result.samples,
        "method": result.method,
    }


@router.post("/editors/{project_id}/translate-captions")
def translate_captions(
    project_id: str,
    payload: CaptionTranslationRequest,
    ctx: RequestContext = Depends(get_context),
):
    ctx.require("editor")
    project = get_editor(ctx, project_id)
    transcript = ctx.db.scalar(
        select(Transcript)
        .where(Transcript.video_id == project.video_id, Transcript.status == "completed")
        .order_by(Transcript.created_at.desc())
    )
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcribe this video before translating captions")
    rows = list(
        ctx.db.scalars(
            select(TranscriptSegment)
            .where(
                TranscriptSegment.transcript_id == transcript.id,
                TranscriptSegment.end_ms > project.trim_start_ms,
                TranscriptSegment.start_ms < project.trim_end_ms,
            )
            .order_by(TranscriptSegment.start_ms)
        )
    )
    if not rows:
        raise HTTPException(status_code=400, detail="There are no caption lines inside this clip range")
    if len(rows) > 600:
        raise HTTPException(status_code=400, detail="This clip has too many caption lines to translate at once")
    try:
        provider = ai_service.build_provider(ctx.db, ctx.workspace.id, payload.provider)
        result = translation.translate_segments(provider, rows, payload.language)
    except (ai_service.AIError, translation.TranslationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    project.caption_translation = result
    ctx.db.commit()
    record_audit(
        ctx.db,
        "editor.translate_captions",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="editing_project",
        target_id=project.id,
        meta={"language": result["language"], "provider": result["provider"]},
        ip_address=ctx.ip_address,
    )
    ctx.db.commit()
    return result


@router.delete("/editors/{project_id}/translate-captions", status_code=204)
def clear_caption_translation(project_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    project = get_editor(ctx, project_id)
    project.caption_translation = {}
    ctx.db.commit()


@router.post("/editors/{project_id}/render", response_model=RenderOut, status_code=202)
def request_render(
    project_id: str,
    payload: RenderRequest,
    ctx: RequestContext = Depends(get_context),
):
    ctx.require("editor")
    project = get_editor(ctx, project_id)
    video = ctx.db.get(SourceVideo, project.video_id)
    if not video or not video.storage_key:
        raise HTTPException(status_code=400, detail="Video file is unavailable for rendering")
    if project.trim_end_ms <= project.trim_start_ms:
        raise HTTPException(status_code=400, detail="Set a valid clip range first")
    if payload.format == "webm" and settings.hwaccel == "nvenc":
        pass  # software fallback is automatic
    # Plan limit: rendered minutes this calendar month.
    from datetime import datetime, timezone

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = ctx.db.scalar(
        select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
            UsageRecord.workspace_id == ctx.workspace.id,
            UsageRecord.kind == "render_seconds",
            UsageRecord.created_at >= month_start,
        )
    ) or 0
    requested_minutes = (project.trim_end_ms - project.trim_start_ms) / 60000
    if (used / 60) + requested_minutes > ctx.workspace.monthly_render_minutes:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Monthly render limit reached ({ctx.workspace.monthly_render_minutes} minutes). "
                "Upgrade the plan or wait for the next cycle."
            ),
        )
    width, height = None, None
    if payload.preset == "custom":
        width = payload.width or project.width
        height = payload.height or project.height
        project.width, project.height = width, height
        project.aspect_ratio = "custom"
    elif payload.width and payload.height:
        width, height = payload.width, payload.height
    if payload.preset not in PRESETS:
        raise HTTPException(status_code=400, detail="Unknown render preset")
    render = RenderJob(
        workspace_id=ctx.workspace.id,
        editing_project_id=project.id,
        created_by=ctx.user.id,
        preset=payload.preset,
        format=payload.format,
        status="queued",
    )
    ctx.db.add(render)
    record_audit(ctx.db, "render.request", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="render_job", target_id=render.id, ip_address=ctx.ip_address,
                 meta={"preset": payload.preset, "format": payload.format})
    ctx.db.commit()
    job = create_pipeline_job(
        ctx.db,
        workspace_id=ctx.workspace.id,
        video_id=video.id,
        kind="rendering",
        task_name="render_video",
        payload={
            "render_job_id": render.id,
            "preset": payload.preset,
            "format": payload.format,
            "width": width,
            "height": height,
        },
    )
    enqueue(job.id)
    return render_out(render, project=project, video=video)


@router.get("/caption-styles", response_model=list[CaptionStyleOut])
def list_caption_styles(ctx: RequestContext = Depends(get_context)):
    rows = ctx.db.scalars(
        select(CaptionStyle).where(
            (CaptionStyle.workspace_id == ctx.workspace.id) | (CaptionStyle.is_builtin.is_(True))
        ).order_by(CaptionStyle.is_builtin.desc(), CaptionStyle.name)
    )
    return list(rows)


@router.post("/caption-styles", response_model=CaptionStyleOut, status_code=201)
def create_caption_style(payload: CaptionStyleCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    style = CaptionStyle(
        workspace_id=ctx.workspace.id,
        name=payload.name.strip()[:80],
        is_builtin=False,
        config=payload.config,
    )
    ctx.db.add(style)
    ctx.db.commit()
    return style
