"""Project (folder) management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from ..deps import RequestContext, get_context, record_audit
from ..models import Project, SourceVideo
from ..schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _out(db, project: Project) -> ProjectOut:
    count = db.scalar(
        select(func.count()).select_from(SourceVideo).where(SourceVideo.project_id == project.id)
    ) or 0
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        video_count=count,
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(ctx: RequestContext = Depends(get_context)):
    rows = ctx.db.scalars(
        select(Project).where(Project.workspace_id == ctx.workspace.id).order_by(Project.created_at.desc())
    )
    return [_out(ctx.db, project) for project in rows]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    project = Project(
        workspace_id=ctx.workspace.id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        created_by=ctx.user.id,
    )
    ctx.db.add(project)
    record_audit(ctx.db, "project.create", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="project", target_id=project.id, ip_address=ctx.ip_address)
    ctx.db.commit()
    return _out(ctx.db, project)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectUpdate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    project = ctx.db.get(Project, project_id)
    if not project or project.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.name is not None:
        project.name = payload.name.strip()
    if payload.description is not None:
        project.description = payload.description.strip()
    ctx.db.commit()
    return _out(ctx.db, project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    project = ctx.db.get(Project, project_id)
    if not project or project.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Project not found")
    for video in ctx.db.scalars(select(SourceVideo).where(SourceVideo.project_id == project.id)):
        video.project_id = None
    ctx.db.delete(project)
    ctx.db.commit()
