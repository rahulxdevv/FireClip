"""Clip review, AI copy generation and hand-off to the editor."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select

from ..deps import RequestContext, get_context, rate_limit, record_audit
from ..models import (
    CandidateClip,
    ClipComment,
    EditingProject,
    ExportedVideo,
    RenderJob,
    SourceVideo,
    Transcript,
    TranscriptSegment,
    User,
    utcnow,
)
from ..schemas import (
    BulkClipRequest,
    ClipContentOut,
    ClipDetail,
    ClipUpdate,
    CommentCreate,
    CommentOut,
    CommentUpdate,
    EditorCreate,
    EditorOut,
)
from ..services import ai as ai_service
from ..services import content as content_service
from ..services.render import ASPECT_SIZES
from ..services.transcription import SegmentData
from ..services.webhooks import emit
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
    counts: dict[str, list[int]] = {}
    if clips:
        rows = ctx.db.execute(
            select(ClipComment.clip_id, ClipComment.resolved_at).where(
                ClipComment.clip_id.in_([clip.id for clip in clips])
            )
        )
        for clip_id, resolved_at in rows:
            entry = counts.setdefault(clip_id, [0, 0])
            entry[0] += 1
            if resolved_at is None:
                entry[1] += 1
    return [
        clip_out(
            clip,
            videos.get(clip.video_id),
            editors.get(clip.id),
            comment_count=counts.get(clip.id, [0, 0])[0],
            open_comment_count=counts.get(clip.id, [0, 0])[1],
        )
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
    comments = list(
        ctx.db.execute(
            select(ClipComment.resolved_at).where(ClipComment.clip_id == clip.id)
        )
    )
    data = clip_out(
        clip,
        video,
        editor,
        render_count,
        comment_count=len(comments),
        open_comment_count=sum(1 for (resolved_at,) in comments if resolved_at is None),
    )
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


@router.post("/bulk")
def bulk_clip_action(payload: BulkClipRequest, ctx: RequestContext = Depends(get_context)):
    """Apply one review action to many clips at once."""
    ctx.require("editor")
    rows = list(
        ctx.db.scalars(
            select(CandidateClip).where(
                CandidateClip.workspace_id == ctx.workspace.id,
                CandidateClip.id.in_(payload.clip_ids),
            )
        )
    )
    if len(rows) != len(set(payload.clip_ids)):
        raise HTTPException(status_code=404, detail="One or more clips were not found")
    if payload.action == "merge":
        if len(rows) < 2:
            raise HTTPException(status_code=400, detail="Select at least two clips to merge")
        return {"action": "merge", "updated": 1, "clip": merge_clips({"clip_ids": payload.clip_ids}, ctx)}
    if payload.action in {"approve", "reject"}:
        status = "approved" if payload.action == "approve" else "rejected"
        for clip in rows:
            clip.status = status
        record_audit(
            ctx.db,
            f"clip.bulk_{payload.action}",
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id,
            target_type="clip",
            target_id=",".join(payload.clip_ids)[:60],
            ip_address=ctx.ip_address,
            meta={"count": len(rows)},
        )
        ctx.db.commit()
        emit(
            ctx.db,
            ctx.workspace.id,
            "clip.approved" if payload.action == "approve" else "clip.rejected",
            {"clip_ids": payload.clip_ids, "count": len(rows)},
        )
        return {"action": payload.action, "updated": len(rows)}
    # delete
    for clip in rows:
        for editor in ctx.db.scalars(select(EditingProject).where(EditingProject.clip_id == clip.id)):
            editor.clip_id = None
        for comment in ctx.db.scalars(select(ClipComment).where(ClipComment.clip_id == clip.id)):
            ctx.db.delete(comment)
    ctx.db.flush()
    for clip in rows:
        ctx.db.delete(clip)
    record_audit(
        ctx.db,
        "clip.bulk_delete",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="clip",
        target_id=",".join(payload.clip_ids)[:60],
        ip_address=ctx.ip_address,
        meta={"count": len(rows)},
    )
    ctx.db.commit()
    return {"action": "delete", "deleted": len(rows)}


@router.get("/{clip_id}/comments", response_model=list[CommentOut])
def list_comments(clip_id: str, ctx: RequestContext = Depends(get_context)):
    clip = get_clip(ctx, clip_id)
    rows = ctx.db.execute(
        select(ClipComment, User)
        .join(User, User.id == ClipComment.user_id)
        .where(ClipComment.clip_id == clip.id)
        .order_by(ClipComment.created_at)
    ).all()
    return [
        CommentOut(
            id=comment.id,
            clip_id=comment.clip_id,
            user_id=comment.user_id,
            author_name=user.name,
            author_email=user.email,
            body=comment.body,
            resolved_at=comment.resolved_at,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            mine=comment.user_id == ctx.user.id,
        )
        for comment, user in rows
    ]


@router.post("/{clip_id}/comments", response_model=CommentOut, status_code=201)
def create_comment(clip_id: str, payload: CommentCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    clip = get_clip(ctx, clip_id)
    comment = ClipComment(
        workspace_id=ctx.workspace.id,
        clip_id=clip.id,
        user_id=ctx.user.id,
        body=payload.body.strip(),
    )
    ctx.db.add(comment)
    record_audit(
        ctx.db,
        "clip.comment",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="clip",
        target_id=clip.id,
        ip_address=ctx.ip_address,
    )
    ctx.db.commit()
    ctx.db.refresh(comment)
    return CommentOut(
        id=comment.id,
        clip_id=comment.clip_id,
        user_id=comment.user_id,
        author_name=ctx.user.name,
        author_email=ctx.user.email,
        body=comment.body,
        resolved_at=None,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        mine=True,
    )


def _get_comment(ctx: RequestContext, clip_id: str, comment_id: str) -> ClipComment:
    comment = ctx.db.get(ClipComment, comment_id)
    if not comment or comment.workspace_id != ctx.workspace.id or comment.clip_id != clip_id:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment


@router.patch("/{clip_id}/comments/{comment_id}", response_model=CommentOut)
def update_comment(
    clip_id: str,
    comment_id: str,
    payload: CommentUpdate,
    ctx: RequestContext = Depends(get_context),
):
    ctx.require("editor")
    comment = _get_comment(ctx, clip_id, comment_id)
    if comment.user_id != ctx.user.id and ctx.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only the author or an admin can edit this comment")
    if payload.body is not None:
        comment.body = payload.body.strip()
    if payload.resolved is not None:
        comment.resolved_at = utcnow() if payload.resolved else None
        comment.resolved_by = ctx.user.id if payload.resolved else None
    comment.updated_at = datetime.now(timezone.utc)
    ctx.db.commit()
    ctx.db.refresh(comment)
    author = ctx.db.get(User, comment.user_id)
    return CommentOut(
        id=comment.id,
        clip_id=comment.clip_id,
        user_id=comment.user_id,
        author_name=author.name if author else "",
        author_email=author.email if author else "",
        body=comment.body,
        resolved_at=comment.resolved_at,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        mine=comment.user_id == ctx.user.id,
    )


@router.delete("/{clip_id}/comments/{comment_id}", status_code=204)
def delete_comment(clip_id: str, comment_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    comment = _get_comment(ctx, clip_id, comment_id)
    if comment.user_id != ctx.user.id and ctx.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only the author or an admin can delete this comment")
    ctx.db.delete(comment)
    ctx.db.commit()


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
    emit(ctx.db, ctx.workspace.id, "clip.approved", {"clip_id": clip.id, "title": clip.title})
    return _detail(ctx, clip)


@router.post("/{clip_id}/reject", response_model=ClipDetail)
def reject_clip(clip_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    clip = get_clip(ctx, clip_id)
    clip.status = "rejected"
    ctx.db.commit()
    emit(ctx.db, ctx.workspace.id, "clip.rejected", {"clip_id": clip.id, "title": clip.title})
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