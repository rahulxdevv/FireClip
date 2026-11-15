"""Workspace-scoped media assets: background music and image overlays."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select

from ..config import settings
from ..deps import RequestContext, get_context
from ..models import SourceVideo
from ..storage import build_key, get_storage, safe_filename
from .media_utils import serve_key

router = APIRouter(prefix="/api/assets", tags=["assets"])

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_AUDIO_BYTES = 60 * 1024 * 1024


@router.post("", status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    kind: str = Form(default="image"),
    ctx: RequestContext = Depends(get_context),
):
    ctx.require("editor")
    if kind not in {"image", "music"}:
        raise HTTPException(status_code=400, detail="kind must be 'image' or 'music'")
    original = safe_filename(file.filename or "asset")
    suffix = Path(original).suffix.lower()
    if kind == "image":
        allowed = set(settings.allowed_image_ext)
        limit = MAX_IMAGE_BYTES
    else:
        allowed = set(settings.allowed_audio_ext)
        limit = MAX_AUDIO_BYTES
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported {kind} type. Allowed: {', '.join(sorted(allowed))}",
        )
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"{kind.title()} exceeds the size limit")
    if not data:
        raise HTTPException(status_code=400, detail="Asset is empty")
    key = build_key("assets", ctx.workspace.id, f"{uuid.uuid4().hex}{suffix}")
    storage = get_storage()
    storage.put_bytes(data, key, file.content_type or "application/octet-stream")
    return {
        "key": key,
        "name": original,
        "kind": kind,
        "size": len(data),
        "url": f"/api/assets/{key}",
    }


@router.get("/{key:path}")
def get_asset(key: str, request: Request, ctx: RequestContext = Depends(get_context)):
    if not key.startswith(f"assets/{ctx.workspace.id}/"):
        raise HTTPException(status_code=404, detail="Asset not found")
    return serve_key(request, key)
