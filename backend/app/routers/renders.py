"""Render queue, pipeline jobs and export library."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from ..deps import RequestContext, get_context
from ..jobs import cancel_job, create_pipeline_job, enqueue
from ..models import EditingProject, ExportedVideo, PipelineJob, RenderJob, SourceVideo
from ..schemas import ExportOut, RenderDetail, RenderOut
from ..storage import get_storage
from .common import export_out, get_editor, get_export, get_render, render_out
from .media_utils import serve_key

router = APIRouter(prefix="/api", tags=["renders"])


@router.get("/renders", response_model=list[RenderDetail])
def list_renders(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=300),
    ctx: RequestContext = Depends(get_context),
):
    query = select(RenderJob).where(RenderJob.workspace_id == ctx.workspace.id)
    if status_filter:
        query = query.where(RenderJob.status == status_filter)
    renders = list(ctx.db.scalars(query.order_by(RenderJob.created_at.desc()).limit(limit)))
    result = []
    for render in renders:
        export = ctx.db.scalar(
            select(ExportedVideo).where(ExportedVideo.render_job_id == render.id).order_by(ExportedVideo.created_at.desc())
        )
        project = ctx.db.get(EditingProject, render.editing_project_id)
        video = ctx.db.get(SourceVideo, project.video_id) if project else None
        result.append(render_out(render, export, project, video))
    return result


@router.get("/renders/{render_id}", response_model=RenderDetail)
def render_detail(render_id: str, ctx: RequestContext = Depends(get_context)):
    render = get_render(ctx, render_id)
    export = ctx.db.scalar(select(ExportedVideo).where(ExportedVideo.render_job_id == render.id))
    project = ctx.db.get(EditingProject, render.editing_project_id)
    video = ctx.db.get(SourceVideo, project.video_id) if project else None
    return render_out(render, export, project, video)


@router.post("/renders/{render_id}/cancel", response_model=RenderOut)
def cancel_render(render_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    render = get_render(ctx, render_id)
    if render.status in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=400, detail="This render has already finished")
    render.status = "cancelled"
    render.error_message = "Cancelled by user"
    for job in ctx.db.scalars(
        select(PipelineJob).where(
            PipelineJob.kind == "rendering",
            PipelineJob.status.in_(["queued", "running"]),
        )
    ):
        if job.payload.get("render_job_id") == render.id:
            cancel_job(ctx.db, job.id, ctx.workspace.id)
    ctx.db.commit()
    return render


@router.post("/renders/{render_id}/retry", response_model=RenderOut, status_code=202)
def retry_render(render_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    render = get_render(ctx, render_id)
    if render.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Only failed or cancelled renders can be retried")
    project = get_editor(ctx, render.editing_project_id)
    video = ctx.db.get(SourceVideo, project.video_id)
    render.status = "queued"
    render.progress = 0
    render.error_message = None
    ctx.db.commit()
    job = create_pipeline_job(
        ctx.db,
        workspace_id=ctx.workspace.id,
        video_id=project.video_id,
        kind="rendering",
        task_name="render_video",
        payload={"render_job_id": render.id, "preset": render.preset, "format": render.format},
    )
    enqueue(job.id)
    return render_out(render, project=project, video=video)


@router.get("/exports", response_model=list[ExportOut])
def list_exports(
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = Depends(get_context),
):
    rows = ctx.db.scalars(
        select(ExportedVideo)
        .where(ExportedVideo.workspace_id == ctx.workspace.id)
        .order_by(ExportedVideo.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [export_out(row) for row in rows]


@router.get("/exports/{export_id}/download")
def download_export(export_id: str, request: Request, ctx: RequestContext = Depends(get_context)):
    export = get_export(ctx, export_id)
    return serve_key(request, export.storage_key, filename=export.filename, inline=False)


@router.get("/exports/{export_id}/thumbnail")
def export_thumbnail(export_id: str, request: Request, ctx: RequestContext = Depends(get_context)):
    export = get_export(ctx, export_id)
    if not export.thumbnail_key:
        raise HTTPException(status_code=404, detail="No thumbnail available")
    return serve_key(request, export.thumbnail_key)


@router.delete("/exports/{export_id}", status_code=204)
def delete_export(export_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    export = get_export(ctx, export_id)
    storage = get_storage()
    for key in (export.storage_key, export.thumbnail_key):
        if key:
            try:
                storage.delete(key)
            except Exception:
                pass
    ctx.db.delete(export)
    ctx.db.commit()


@router.get("/jobs")
def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=60, ge=1, le=200),
    ctx: RequestContext = Depends(get_context),
):
    query = select(PipelineJob).where(PipelineJob.workspace_id == ctx.workspace.id)
    if status_filter:
        query = query.where(PipelineJob.status == status_filter)
    jobs = ctx.db.scalars(query.order_by(PipelineJob.created_at.desc()).limit(limit))
    return [
        {
            "id": job.id,
            "video_id": job.video_id,
            "kind": job.kind,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "attempts": job.attempts,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }
        for job in jobs
    ]


@router.post("/jobs/{job_id}/cancel")
def cancel_pipeline_job(job_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    if not cancel_job(ctx.db, job_id, ctx.workspace.id):
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")
    return {"status": "cancelled"}
