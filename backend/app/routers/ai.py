"""AI provider configuration and diagnostics."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from ..deps import RequestContext, get_context, record_audit
from ..models import AiProviderConfig
from ..schemas import AiProviderOut, AiProviderUpdate, AiTestRequest, AiTestResult
from ..security import encrypt_secret, mask_secret
from ..services import ai as ai_service
from ..services import transcription

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/providers", response_model=list[AiProviderOut])
def list_providers(ctx: RequestContext = Depends(get_context)):
    configs = {
        row.provider: row
        for row in ctx.db.scalars(
            select(AiProviderConfig).where(AiProviderConfig.workspace_id == ctx.workspace.id)
        )
    }
    result = []
    for info in ai_service.provider_infos(ctx.db, ctx.workspace.id):
        row = configs.get(info.provider)
        cls, label, _model, _base, _key, local, caps = ai_service.PROVIDERS[info.provider]
        workspace_key = bool(row and row.api_key_encrypted)
        result.append(
            AiProviderOut(
                provider=info.provider,
                label=label,
                model=info.model,
                base_url=info.base_url,
                configured=info.configured,
                has_workspace_key=workspace_key,
                enabled=row.enabled if row else True,
                is_default=bool(row and row.is_default),
                capabilities=caps,
                local=local,
            )
        )
    result.append(
        AiProviderOut(
            provider="heuristic",
            label="Built-in signal engine",
            model="fireclip-signals-v1",
            base_url="",
            configured=True,
            has_workspace_key=False,
            enabled=True,
            is_default=False,
            capabilities=["analysis", "copy", "offline"],
            local=True,
        )
    )
    return result


@router.put("/providers", response_model=AiProviderOut)
def update_provider(payload: AiProviderUpdate, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    row = ctx.db.scalar(
        select(AiProviderConfig).where(
            AiProviderConfig.workspace_id == ctx.workspace.id,
            AiProviderConfig.provider == payload.provider,
        )
    )
    if not row:
        row = AiProviderConfig(workspace_id=ctx.workspace.id, provider=payload.provider)
        ctx.db.add(row)
    row.model = payload.model.strip()
    row.base_url = payload.base_url.strip()
    row.enabled = payload.enabled
    if payload.api_key is not None:
        row.api_key_encrypted = encrypt_secret(payload.api_key.strip()) if payload.api_key.strip() else ""
    if payload.is_default:
        for other in ctx.db.scalars(
            select(AiProviderConfig).where(AiProviderConfig.workspace_id == ctx.workspace.id)
        ):
            other.is_default = other.provider == payload.provider
    row.is_default = payload.is_default
    record_audit(ctx.db, "ai.provider_update", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="ai_provider", target_id=row.id, ip_address=ctx.ip_address,
                 meta={"provider": payload.provider, "model": row.model,
                       "key": mask_secret(payload.api_key or "") if payload.api_key else "unchanged"})
    ctx.db.commit()
    cls, label, _model, _base, _key, local, caps = ai_service.PROVIDERS[payload.provider]
    info = {i.provider: i for i in ai_service.provider_infos(ctx.db, ctx.workspace.id)}[payload.provider]
    return AiProviderOut(
        provider=info.provider,
        label=label,
        model=info.model,
        base_url=info.base_url,
        configured=info.configured,
        has_workspace_key=bool(row.api_key_encrypted),
        enabled=row.enabled,
        is_default=row.is_default,
        capabilities=caps,
        local=local,
    )


@router.post("/test", response_model=AiTestResult)
def test_provider(payload: AiTestRequest, ctx: RequestContext = Depends(get_context)):
    ok, message, latency = ai_service.test_provider(ctx.db, ctx.workspace.id, payload.provider)
    return AiTestResult(provider=payload.provider, ok=ok, message=message, latency_ms=latency)


@router.get("/transcription")
def transcription_engines(ctx: RequestContext = Depends(get_context)):
    return {
        "configured": ctx.workspace.id and __import__("app.config", fromlist=["settings"]).settings.transcription_engine,
        "engines": transcription.engine_status(),
        "diarization": __import__("app.config", fromlist=["settings"]).settings.diarization_mode,
    }
