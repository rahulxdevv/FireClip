"""Clip review, AI copy generation and hand-off to the editor."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select

from ..deps import RequestContext, get_context, rate_limit, record_audit
from ..models import CandidateClip, EditingProject, ExportedVideo, RenderJob, SourceVideo, Transcript, TranscriptSegment
from ..schemas import ClipContentOut, ClipDetail, ClipUpdate, EditorCreate, EditorOut
from ..services import ai as ai_service
from ..services import content as content_service
from ..services.render import ASPECT_SIZES
from ..services.transcription import SegmentData
from .common import clip_out, get_clip, get_video

router = APIRouter(prefix="/api/clips", tags=["clips"])


@router.get("", response_model=list[ClipDetail])
def list_clips(
    status_filter: str | None = Query(default=None, alias="status"),
    video_id: str | None = None,
    sort: str = Query(default="score", pattern="^(score|recent|duration)$"),
    search: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    ctx: RequestContext = Depends(get_context),
):
    query = select(CandidateClip).where(CandidateClip.workspace_id == ctx.workspace.id)
    if status_filter:
        query = query.where(CandidateClip.status == status_filter)
    if video_id:
        query = query.where(CandidateClip.video_id == video_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(CandidateClip.title.ilike(term), CandidateClip.transcript_text.ilike(term)))
    if sort == "score":
        query = query.order_by(CandidateClip.virality_score.desc())
    elif sort == "duration":
        query = query.order_by(CandidateClip.duration_ms.desc())
    else:
        query = query.order_by(CandidateClip.created_at.desc())
    clips = list(ctx.db.scalars(query.limit(limit)))
    video_ids = {clip.video_id for clip in clips}
    videos = {
        video.id: video
        for video in ctx.db.scalars(select(SourceVideo).where(SourceVideo.id.in_(video_ids)))
    } if video_ids else {}
    editors = {
        editor.clip_id: editor
        for editor in ctx.db.scalars(
            select(EditingProject).where(EditingProject.workspace_id == ctx.workspace.id)
        )
        if editor.clip_id
    }
    return [
        clip_out(clip, videos.get(clip.video_id), editors.get(clip.id))
        for clip in clips
    ]


def _detail(ctx: RequestContext, clip: CandidateClip) -> dict:
    video = ctx.db.get(SourceVideo, clip.video_id)
    editor = ctx.db.scalar(
        select(EditingProject).where(EditingProject.clip_id == clip.id).order_by(EditingProject.created_at.desc())
    )
    render_count = 0
    if editor:
        render_count = len(
            list(ctx.db.scalars(select(RenderJob.id).where(RenderJob.editing_project_id == editor.id)))
        )
    data = clip_out(clip, video, editor, render_count)
    return data


@router.post("/merge", response_model=ClipDetail, status_code=201)
def merge_clips(payload: dict, ctx: RequestContext = Depends(get_context)):
    """Merge two or more adjacent clips from the same video into one longer clip."""
    ctx.require("editor")
    clip_ids = payload.get("clip_ids")
    if not isinstance(clip_ids, list) or len(clip_ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least two clips to merge")
    if len(clip_ids) > 20:
        raise HTTPException(status_code=400, detail="Merge at most 20 clips at once")
    rows = list(
        ctx.db.scalars(
            select(CandidateClip).where(
                CandidateClip.workspace_id == ctx.workspace.id, CandidateClip.id.in_(clip_ids)
            )
        )
    )
    if len(rows) != len(set(clip_ids)):
        raise HTTPException(status_code=404, detail="One or more clips were not found")
    video_ids = {row.video_id for row in rows}
    if len(video_ids) != 1:
        raise HTTPException(status_code=400, detail="Clips must come from the same video")
    ordered = sorted(rows, key=lambda row: row.start_ms)
    start = ordered[0].start_ms
    end = max(row.end_ms for row in ordered)
    video = ctx.db.get(SourceVideo, ordered[0].video_id)
    title = order_title = ordered[0].title
    if len(ordered) > 1:
        title = f"{order_title.rsplit(' - part', 1)[0]} - merged"
    merged = CandidateClip(
        workspace_id=ctx.workspace.id,
        video_id=ordered[0].video_id,
        start_ms=start,
        end_ms=end,
        duration_ms=end - start,
        title=title[:240],
        description=" ".join(row.description for row in ordered)[:1200],
        hook=ordered[0].hook,
        transcript_text=" ".join(row.transcript_text for row in ordered).strip(),
        explanation="Merged by a team member from " + str(len(ordered)) + " adjacent clip candidates.",
        virality_score=max(row.virality_score for row in ordered),
        engagement_potential=max(row.engagement_potential for row in ordered),
        signals={},
        aspect_ratio=ordered[0].aspect_ratio,
        source="manual",
        status="suggested",
    )
    ctx.db.add(merged)
    for row in ordered:
        for editor in ctx.db.scalars(select(EditingProject).where(EditingProject.clip_id == row.id)):
            editor.clip_id = None
        ctx.db.delete(row)
    record_audit(ctx.db, "clip.merge", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="clip", target_id=merged.id, ip_address=ctx.ip_address,
                 meta={"source_clips": clip_ids})
    ctx.db.commit()
    return _detail(ctx, merged)


@router.get("/{clip_id}", response_model=ClipDetail)
def get_clip_detail(clip_id: str, ctx: RequestContext = Depends(get_context)):
    return _detail(ctx, get_clip(ctx, clip_id))


@router.patch("/{clip_id}", response_model=ClipDetail)
def update_clip(clip_id: str, payload: ClipUpdate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    clip = get_clip(ctx, clip_id)
    video = ctx.db.get(SourceVideo, clip.video_id)
    if payload.title is not None:
        clip.title = payload.title.strip()
    if payload.description is not None:
        clip.description = payload.description
    if payload.hook is not None:
        clip.hook = payload.hook
    if payload.start_ms is not None:
        clip.start_ms = payload.start_ms
    if payload.end_ms is not None:
        clip.end_ms = payload.end_ms
    if payload.aspect_ratio is not None:
        clip.aspect_ratio = payload.aspect_ratio
    if payload.status is not None:
        clip.status = payload.status
    if clip.end_ms <= clip.start_ms:
        raise HTTPException(status_code=400, detail="End must be after start")
    if video and video.duration_seconds and clip.end_ms > int(video.duration_seconds * 1000) + 500:
        raise HTTPException(status_code=400, detail="Clip range exceeds the video duration")
    clip.duration_ms = clip.end_ms - clip.start_ms
    ctx.db.commit()
    return _detail(ctx, clip)


@router.delete("/{clip_id}", status_code=204)
def delete_clip(clip_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    clip = get_clip(ctx, clip_id)
    for editor in ctx.db.scalars(select(EditingProject).where(EditingProject.clip_id == clip.id)):
        editor.clip_id = None
    ctx.db.delete(clip)
    ctx.db.commit()


@router.post("/{clip_id}/approve", response_model=ClipDetail)
def approve_clip(clip_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    clip = get_clip(ctx, clip_id)
    clip.status = "approved"
    ctx.db.commit()
    return _detail(ctx, clip)


@router.post("/{clip_id}/reject", response_model=ClipDetail)
def reject_clip(clip_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    clip = get_clip(ctx, clip_id)
    clip.status = "rejected"
    ctx.db.commit()
    return _detail(ctx, clip)


@router.post("/{clip_id}/content", response_model=ClipContentOut)
def generate_content(
    clip_id: str,
    provider: str = Query(default="auto"),
    refresh: bool = Query(default=False),
    ctx: RequestContext = Depends(get_context),
    _limit=Depends(rate_limit("content", 30)),
):
    clip = get_clip(ctx, clip_id)
    if clip.content and not refresh:
        return {**clip.content, "provider": clip.content.get("provider", "cached"), "model": clip.content.get("model", "")}
    video = ctx.db.get(SourceVideo, clip.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Source video not found")
    segments: list[SegmentData] = []
    transcript = ctx.db.scalar(
        select(Transcript)
        .where(Transcript.video_id == video.id, Transcript.status == "completed")
        .order_by(Transcript.created_at.desc())
    )
    if transcript:
        for row in ctx.db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.start_ms)
        ):
            segments.append(SegmentData(start_ms=row.start_ms, end_ms=row.end_ms, text=row.text, words=row.words or []))
    try:
        llm = ai_service.build_provider(ctx.db, ctx.workspace.id, provider)
        result = content_service.generate(llm, clip, segments, video)
    except ai_service.AIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    clip.content = result
    ctx.db.commit()
    return result


@router.post("/{clip_id}/editor", response_model=EditorOut)
def create_editor(clip_id: str, payload: EditorCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    clip = get_clip(ctx, clip_id)
    existing = ctx.db.scalar(
        select(EditingProject)
        .where(EditingProject.clip_id == clip.id)
        .order_by(EditingProject.created_at.desc())
    )
    if existing:
        return existing
    aspect = payload.aspect_ratio or clip.aspect_ratio or "9:16"
    width, height = ASPECT_SIZES.get(aspect, (1080, 1920))
    project = EditingProject(
        workspace_id=ctx.workspace.id,
        video_id=clip.video_id,
        clip_id=clip.id,
        created_by=ctx.user.id,
        name=payload.name or clip.title,
        aspect_ratio=aspect,
        width=width,
        height=height,
        trim_start_ms=clip.start_ms,
        trim_end_ms=clip.end_ms,
        focus_x=0.5,
        focus_y=0.45,
        audio={"volume": 1.0, "muted": False},
        overlays=[],
        operations=[],
    )
    ctx.db.add(project)
    record_audit(ctx.db, "editor.create", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="editing_project", target_id=project.id, ip_address=ctx.ip_address,
                 meta={"clip_id": clip.id})
    ctx.db.commit()
    return project
