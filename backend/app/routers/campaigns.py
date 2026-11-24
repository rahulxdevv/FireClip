"""Campaigns group source videos under one reusable production brief."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select

from ..deps import RequestContext, get_context, record_audit
from ..jobs import create_pipeline_job, enqueue
from ..models import (
    Campaign,
    CandidateClip,
    CaptionStyle,
    EditingProject,
    RenderJob,
    SourceVideo,
)
from ..schemas import (
    CampaignAnalyzeRequest,
    CampaignCreate,
    CampaignDetail,
    CampaignOut,
    CampaignUpdate,
    CampaignVideoAdd,
)

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def _campaign(ctx: RequestContext, campaign_id: str) -> Campaign:
    campaign = ctx.db.get(Campaign, campaign_id)
    if not campaign or campaign.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def _validate_style(ctx: RequestContext, style_id: str | None) -> None:
    if not style_id:
        return
    style = ctx.db.get(CaptionStyle, style_id)
    if not style or (style.workspace_id != ctx.workspace.id and not style.is_builtin):
        raise HTTPException(status_code=400, detail="Caption style not found in this workspace")


_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _clean_brand(brand: dict | None) -> dict:
    if not brand:
        return {}
    allowed = {"accent_color", "secondary_color", "font", "logo_text", "watermark", "cta"}
    unknown = set(brand) - allowed
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown brand fields: {', '.join(sorted(unknown))}")
    cleaned: dict[str, str] = {}
    for key, value in brand.items():
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"Brand field {key} must be text")
        value = value.strip()[:200]
        if key in {"accent_color", "secondary_color"} and value and not _HEX_COLOR.fullmatch(value):
            raise HTTPException(status_code=422, detail=f"Brand field {key} must be a hex color")
        cleaned[key] = value
    return cleaned


def _stats(ctx: RequestContext, campaign_ids: list[str]) -> dict[str, dict]:
    if not campaign_ids:
        return {}
    stats = {
        cid: {"video_count": 0, "clip_count_actual": 0, "approved_count": 0, "rendered_count": 0, "source_minutes": 0.0}
        for cid in campaign_ids
    }
    video_rows = ctx.db.execute(
        select(
            SourceVideo.campaign_id,
            func.count(SourceVideo.id),
            func.coalesce(func.sum(SourceVideo.duration_seconds), 0),
        )
        .where(SourceVideo.workspace_id == ctx.workspace.id, SourceVideo.campaign_id.in_(campaign_ids))
        .group_by(SourceVideo.campaign_id)
    ).all()
    for cid, count, seconds in video_rows:
        stats[cid]["video_count"] = int(count)
        stats[cid]["source_minutes"] = round(float(seconds or 0) / 60, 1)
    clip_rows = ctx.db.execute(
        select(
            SourceVideo.campaign_id,
            func.count(CandidateClip.id),
            func.coalesce(func.sum(case((CandidateClip.status == "approved", 1), else_=0)), 0),
        )
        .join(CandidateClip, CandidateClip.video_id == SourceVideo.id)
        .where(SourceVideo.workspace_id == ctx.workspace.id, SourceVideo.campaign_id.in_(campaign_ids))
        .group_by(SourceVideo.campaign_id)
    ).all()
    for cid, count, approved in clip_rows:
        stats[cid]["clip_count_actual"] = int(count)
        stats[cid]["approved_count"] = int(approved or 0)
    render_rows = ctx.db.execute(
        select(EditingProject.campaign_id, func.count(RenderJob.id))
        .join(RenderJob, RenderJob.editing_project_id == EditingProject.id)
        .where(
            EditingProject.workspace_id == ctx.workspace.id,
            EditingProject.campaign_id.in_(campaign_ids),
            RenderJob.status == "completed",
        )
        .group_by(EditingProject.campaign_id)
    ).all()
    for cid, count in render_rows:
        stats[cid]["rendered_count"] = int(count)
    return stats


def _out(ctx: RequestContext, campaign: Campaign, stats: dict | None = None) -> CampaignOut:
    values = stats or _stats(ctx, [campaign.id]).get(campaign.id, {})
    style = ctx.db.get(CaptionStyle, campaign.caption_style_id) if campaign.caption_style_id else None
    return CampaignOut(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        brief=campaign.brief,
        status=campaign.status,
        aspect_ratio=campaign.aspect_ratio,
        target_duration_ms=campaign.target_duration_ms,
        clip_count=campaign.clip_count,
        min_score=campaign.min_score,
        caption_style_id=campaign.caption_style_id,
        caption_overrides=dict(campaign.caption_overrides or {}),
        auto_approve=campaign.auto_approve,
        auto_render=campaign.auto_render,
        brand=dict(campaign.brand or {}),
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        caption_style_name=style.name if style else "",
        video_count=int(values.get("video_count", 0)),
        clip_count_actual=int(values.get("clip_count_actual", 0)),
        approved_count=int(values.get("approved_count", 0)),
        rendered_count=int(values.get("rendered_count", 0)),
        source_minutes=float(values.get("source_minutes", 0.0)),
    )


@router.get("", response_model=list[CampaignOut])
def list_campaigns(ctx: RequestContext = Depends(get_context)):
    rows = list(
        ctx.db.scalars(
            select(Campaign)
            .where(Campaign.workspace_id == ctx.workspace.id)
            .order_by(Campaign.created_at.desc())
        )
    )
    stats = _stats(ctx, [row.id for row in rows])
    return [_out(ctx, row, stats.get(row.id)) for row in rows]


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    if payload.auto_render and not payload.auto_approve:
        raise HTTPException(status_code=422, detail="Automatic rendering requires automatic approval")
    _validate_style(ctx, payload.caption_style_id)
    campaign = Campaign(
        workspace_id=ctx.workspace.id,
        created_by=ctx.user.id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        brief=payload.brief.strip(),
        status=payload.status,
        aspect_ratio=payload.aspect_ratio,
        target_duration_ms=payload.target_duration_ms,
        clip_count=payload.clip_count,
        min_score=payload.min_score,
        caption_style_id=payload.caption_style_id,
        caption_overrides=payload.caption_overrides,
        auto_approve=payload.auto_approve,
        auto_render=payload.auto_render,
        brand=_clean_brand(payload.brand),
    )
    ctx.db.add(campaign)
    ctx.db.commit()
    record_audit(
        ctx.db,
        "campaign.create",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="campaign",
        target_id=campaign.id,
        ip_address=ctx.ip_address,
    )
    ctx.db.commit()
    return _out(ctx, campaign)


@router.get("/{campaign_id}", response_model=CampaignDetail)
def get_campaign(campaign_id: str, ctx: RequestContext = Depends(get_context)):
    campaign = _campaign(ctx, campaign_id)
    videos = list(
        ctx.db.scalars(
            select(SourceVideo)
            .where(SourceVideo.campaign_id == campaign.id)
            .order_by(SourceVideo.created_at.desc())
        )
    )
    clips = list(
        ctx.db.scalars(
            select(CandidateClip)
            .join(SourceVideo, SourceVideo.id == CandidateClip.video_id)
            .where(SourceVideo.campaign_id == campaign.id)
            .order_by(CandidateClip.virality_score.desc(), CandidateClip.created_at.desc())
        )
    )
    base = _out(ctx, campaign)
    return CampaignDetail(
        **base.model_dump(),
        videos=videos,
        clips=clips,
    )


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: str, payload: CampaignUpdate, ctx: RequestContext = Depends(get_context)
):
    ctx.require("editor")
    campaign = _campaign(ctx, campaign_id)
    if "caption_style_id" in payload.model_fields_set:
        _validate_style(ctx, payload.caption_style_id)
    if "name" in payload.model_fields_set and payload.name is not None:
        campaign.name = payload.name.strip()
    if "description" in payload.model_fields_set and payload.description is not None:
        campaign.description = payload.description.strip()
    if "brief" in payload.model_fields_set and payload.brief is not None:
        campaign.brief = payload.brief.strip()
    if "status" in payload.model_fields_set and payload.status is not None:
        campaign.status = payload.status
    if "aspect_ratio" in payload.model_fields_set and payload.aspect_ratio is not None:
        campaign.aspect_ratio = payload.aspect_ratio
    if "target_duration_ms" in payload.model_fields_set and payload.target_duration_ms is not None:
        campaign.target_duration_ms = payload.target_duration_ms
    if "clip_count" in payload.model_fields_set and payload.clip_count is not None:
        campaign.clip_count = payload.clip_count
    if "min_score" in payload.model_fields_set and payload.min_score is not None:
        campaign.min_score = payload.min_score
    if "caption_style_id" in payload.model_fields_set:
        campaign.caption_style_id = payload.caption_style_id
    if "caption_overrides" in payload.model_fields_set and payload.caption_overrides is not None:
        campaign.caption_overrides = payload.caption_overrides
    if "auto_approve" in payload.model_fields_set and payload.auto_approve is not None:
        campaign.auto_approve = payload.auto_approve
    if "auto_render" in payload.model_fields_set and payload.auto_render is not None:
        campaign.auto_render = payload.auto_render
    if campaign.auto_render and not campaign.auto_approve:
        raise HTTPException(status_code=422, detail="Automatic rendering requires automatic approval")
    if "brand" in payload.model_fields_set:
        campaign.brand = _clean_brand(payload.brand)
    ctx.db.commit()
    record_audit(
        ctx.db,
        "campaign.update",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="campaign",
        target_id=campaign.id,
        ip_address=ctx.ip_address,
    )
    ctx.db.commit()
    return _out(ctx, campaign)


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    campaign = _campaign(ctx, campaign_id)
    for video in ctx.db.scalars(select(SourceVideo).where(SourceVideo.campaign_id == campaign.id)):
        video.campaign_id = None
    for project in ctx.db.scalars(select(EditingProject).where(EditingProject.campaign_id == campaign.id)):
        project.campaign_id = None
    ctx.db.delete(campaign)
    record_audit(
        ctx.db,
        "campaign.delete",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="campaign",
        target_id=campaign.id,
        ip_address=ctx.ip_address,
    )
    ctx.db.commit()


@router.post("/{campaign_id}/videos", response_model=CampaignDetail)
def add_videos(
    campaign_id: str, payload: CampaignVideoAdd, ctx: RequestContext = Depends(get_context)
):
    ctx.require("editor")
    campaign = _campaign(ctx, campaign_id)
    videos = list(
        ctx.db.scalars(
            select(SourceVideo).where(
                SourceVideo.id.in_(payload.video_ids),
                SourceVideo.workspace_id == ctx.workspace.id,
            )
        )
    )
    found = {video.id for video in videos}
    missing = [video_id for video_id in payload.video_ids if video_id not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"Video not found: {missing[0]}")
    for video in videos:
        video.campaign_id = campaign.id
    ctx.db.commit()
    return get_campaign(campaign.id, ctx)


@router.delete("/{campaign_id}/videos/{video_id}", response_model=CampaignDetail)
def remove_video(campaign_id: str, video_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    campaign = _campaign(ctx, campaign_id)
    video = ctx.db.get(SourceVideo, video_id)
    if not video or video.workspace_id != ctx.workspace.id or video.campaign_id != campaign.id:
        raise HTTPException(status_code=404, detail="Video is not in this campaign")
    video.campaign_id = None
    ctx.db.commit()
    return get_campaign(campaign.id, ctx)


@router.post("/{campaign_id}/analyze", status_code=202)
def analyze_campaign(
    campaign_id: str, payload: CampaignAnalyzeRequest, ctx: RequestContext = Depends(get_context)
):
    ctx.require("editor")
    campaign = _campaign(ctx, campaign_id)
    query = select(SourceVideo).where(
        SourceVideo.campaign_id == campaign.id,
        SourceVideo.workspace_id == ctx.workspace.id,
    )
    if payload.video_ids:
        query = query.where(SourceVideo.id.in_(payload.video_ids))
    videos = list(ctx.db.scalars(query))
    if not videos:
        raise HTTPException(status_code=400, detail="Add a video to this campaign first")
    queued = 0
    for video in videos:
        job = create_pipeline_job(
            ctx.db,
            workspace_id=ctx.workspace.id,
            video_id=video.id,
            kind="transcribing",
            task_name="transcribe_video",
            payload={
                "video_id": video.id,
                "auto_analyze": True,
                "force": False,
                "campaign_id": campaign.id,
                "replace_existing": payload.replace_existing,
            },
        )
        enqueue(job.id)
        queued += 1
    return {"queued": queued, "campaign_id": campaign.id}
