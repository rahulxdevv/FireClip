"""Shared router helpers."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    CandidateClip,
    EditingProject,
    ExportedVideo,
    RenderJob,
    SourceVideo,
    Transcript,
)
from ..deps import RequestContext


def get_video(ctx: RequestContext, video_id: str) -> SourceVideo:
    video = ctx.db.get(SourceVideo, video_id)
    if not video or video.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


def get_clip(ctx: RequestContext, clip_id: str) -> CandidateClip:
    clip = ctx.db.get(CandidateClip, clip_id)
    if not clip or clip.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip


def get_editor(ctx: RequestContext, project_id: str) -> EditingProject:
    project = ctx.db.get(EditingProject, project_id)
    if not project or project.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Editing project not found")
    return project


def get_render(ctx: RequestContext, render_id: str) -> RenderJob:
    render = ctx.db.get(RenderJob, render_id)
    if not render or render.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Render job not found")
    return render


def get_export(ctx: RequestContext, export_id: str) -> ExportedVideo:
    export = ctx.db.get(ExportedVideo, export_id)
    if not export or export.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Export not found")
    return export


def video_out(video: SourceVideo) -> dict:
    return {
        "id": video.id,
        "workspace_id": video.workspace_id,
        "project_id": video.project_id,
        "title": video.title,
        "description": video.description,
        "source_type": video.source_type,
        "source_url": video.source_url,
        "original_filename": video.original_filename,
        "mime_type": video.mime_type,
        "size_bytes": video.size_bytes,
        "duration_seconds": video.duration_seconds,
        "width": video.width,
        "height": video.height,
        "fps": video.fps,
        "has_audio": video.has_audio,
        "language": video.language,
        "status": video.status,
        "progress": video.progress,
        "error_message": video.error_message,
        "thumbnail_key": video.thumbnail_key,
        "created_at": video.created_at,
        "updated_at": video.updated_at,
    }


def video_detail(db: Session, video: SourceVideo) -> dict:
    transcript = db.scalar(
        select(Transcript)
        .where(Transcript.video_id == video.id, Transcript.status == "completed")
        .order_by(Transcript.created_at.desc())
    )
    clips = db.scalars(select(CandidateClip).where(CandidateClip.video_id == video.id)).all()
    from ..models import AiAnalysis

    analysis = db.scalar(
        select(AiAnalysis)
        .where(AiAnalysis.video_id == video.id, AiAnalysis.status == "completed")
        .order_by(AiAnalysis.created_at.desc())
    )
    data = video_out(video)
    data.update(
        {
            "has_transcript": bool(transcript),
            "transcript_language": transcript.language if transcript else None,
            "clip_count": len(clips),
            "approved_clip_count": sum(1 for clip in clips if clip.status == "approved"),
            "analysis_provider": analysis.provider if analysis else None,
            "metadata": (video.metadata_row.raw_json if video.metadata_row else None),
        }
    )
    return data


def clip_out(clip: CandidateClip, video: SourceVideo | None = None, editor: EditingProject | None = None,
             render_count: int = 0) -> dict:
    return {
        "id": clip.id,
        "video_id": clip.video_id,
        "workspace_id": clip.workspace_id,
        "start_ms": clip.start_ms,
        "end_ms": clip.end_ms,
        "duration_ms": clip.duration_ms,
        "title": clip.title,
        "description": clip.description,
        "hook": clip.hook,
        "transcript_text": clip.transcript_text,
        "explanation": clip.explanation,
        "virality_score": clip.virality_score,
        "engagement_potential": clip.engagement_potential,
        "signals": clip.signals or {},
        "aspect_ratio": clip.aspect_ratio,
        "source": clip.source,
        "status": clip.status,
        "created_at": clip.created_at,
        "video_title": video.title if video else "",
        "video_duration_seconds": video.duration_seconds if video else 0,
        "has_editing_project": editor is not None,
        "editing_project_id": editor.id if editor else None,
        "render_count": render_count,
    }


def render_out(render: RenderJob, export: ExportedVideo | None = None, project: EditingProject | None = None,
               video: SourceVideo | None = None) -> dict:
    data = {
        "id": render.id,
        "editing_project_id": render.editing_project_id,
        "preset": render.preset,
        "format": render.format,
        "status": render.status,
        "progress": render.progress,
        "attempts": render.attempts,
        "error_message": render.error_message,
        "output_size_bytes": render.output_size_bytes,
        "render_seconds": render.render_seconds,
        "created_at": render.created_at,
        "started_at": render.started_at,
        "finished_at": render.finished_at,
        "export_id": export.id if export else None,
        "download_url": f"/api/exports/{export.id}/download" if export else None,
        "thumbnail_url": f"/api/exports/{export.id}/thumbnail" if export else None,
        "project_name": project.name if project else "",
        "video_title": video.title if video else "",
    }
    return data


def export_out(export: ExportedVideo) -> dict:
    return {
        "id": export.id,
        "render_job_id": export.render_job_id,
        "clip_id": export.clip_id,
        "title": export.title,
        "filename": export.filename,
        "format": export.format,
        "width": export.width,
        "height": export.height,
        "duration_ms": export.duration_ms,
        "size_bytes": export.size_bytes,
        "created_at": export.created_at,
        "download_url": f"/api/exports/{export.id}/download",
        "thumbnail_url": f"/api/exports/{export.id}/thumbnail",
    }
