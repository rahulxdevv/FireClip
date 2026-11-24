"""Public share links for exported clips."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from ..config import settings
from ..deps import RequestContext, enforce_rate_limit, get_context, record_audit
from ..models import ExportedVideo, ShareLink, utcnow
from ..schemas import ShareCreate, ShareOut, ShareUnlock
from ..security import create_token, decode_token, hash_password, verify_password
from ..services.webhooks import emit
from .common import get_export
from .media_utils import serve_key

router = APIRouter(prefix="/api", tags=["sharing"])


def _share_url(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/share/{token}"


def _alive(share: ShareLink) -> bool:
    if share.revoked_at:
        return False
    if share.expires_at:
        expires = share.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return False
    return True


def _share_out(share: ShareLink) -> ShareOut:
    return ShareOut(
        id=share.id,
        token=share.token,
        url=_share_url(share.token),
        has_password=bool(share.password_hash),
        expires_at=share.expires_at,
        view_count=share.view_count,
        created_at=share.created_at,
    )


def _load_share(db, token: str) -> tuple[ShareLink, ExportedVideo]:
    share = db.scalar(select(ShareLink).where(ShareLink.token == token))
    if not share or not _alive(share):
        raise HTTPException(status_code=404, detail="This link is invalid, expired or has been revoked")
    export = db.get(ExportedVideo, share.exported_video_id)
    if not export:
        raise HTTPException(status_code=404, detail="The shared clip is no longer available")
    return share, export


def _authorize(share: ShareLink, access: str | None, password: str | None) -> None:
    if access:
        payload = decode_token(access, "share")
        if payload and payload.get("sub") == share.id:
            return
    if share.password_hash:
        if not password or not verify_password(password, share.password_hash):
            raise HTTPException(status_code=403, detail="This link is password protected")
    # No password configured: possession of the link is the credential.


def _media_payload(export: ExportedVideo, token: str, access: str) -> dict:
    suffix = f"?access={access}"
    return {
        "title": export.title,
        "filename": export.filename,
        "format": export.format,
        "width": export.width,
        "height": export.height,
        "duration_ms": export.duration_ms,
        "size_bytes": export.size_bytes,
        "created_at": export.created_at,
        "media_url": f"/api/public/shares/{token}/media{suffix}",
        "download_url": f"/api/public/shares/{token}/download{suffix}",
        "thumbnail_url": f"/api/public/shares/{token}/thumbnail{suffix}",
    }


@router.post("/exports/{export_id}/shares", response_model=ShareOut, status_code=201)
def create_share(export_id: str, payload: ShareCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    export = get_export(ctx, export_id)
    token = secrets.token_urlsafe(24)
    share = ShareLink(
        workspace_id=ctx.workspace.id,
        exported_video_id=export.id,
        created_by=ctx.user.id,
        token=token,
        password_hash=hash_password(payload.password) if payload.password else "",
        expires_at=(
            datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
            if payload.expires_in_days
            else None
        ),
    )
    ctx.db.add(share)
    record_audit(
        ctx.db,
        "share.create",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="export",
        target_id=export.id,
        ip_address=ctx.ip_address,
        meta={"expires_in_days": payload.expires_in_days, "password": bool(payload.password)},
    )
    ctx.db.commit()
    ctx.db.refresh(share)
    emit(
        ctx.db,
        ctx.workspace.id,
        "share.created",
        {"share_id": share.id, "export_id": export.id, "title": export.title},
    )
    return _share_out(share)


@router.get("/exports/{export_id}/shares", response_model=list[ShareOut])
def list_shares(export_id: str, ctx: RequestContext = Depends(get_context)):
    export = get_export(ctx, export_id)
    rows = ctx.db.scalars(
        select(ShareLink)
        .where(ShareLink.exported_video_id == export.id, ShareLink.revoked_at.is_(None))
        .order_by(ShareLink.created_at.desc())
    )
    return [_share_out(row) for row in rows if _alive(row)]


@router.delete("/shares/{share_id}", status_code=204)
def revoke_share(share_id: str, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    share = ctx.db.get(ShareLink, share_id)
    if not share or share.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Share link not found")
    share.revoked_at = utcnow()
    record_audit(
        ctx.db,
        "share.revoke",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="share",
        target_id=share.id,
        ip_address=ctx.ip_address,
    )
    ctx.db.commit()


@router.get("/public/shares/{token}")
def public_share(token: str):
    # Public routes open their own session so they never require a signed-in user.
    from ..database import session_scope

    with session_scope() as db:
        share, export = _load_share(db, token)
        if share.password_hash:
            return {
                "locked": True,
                "token": token,
                "has_password": True,
                "expires_at": share.expires_at,
            }
        access = create_token(share.id, "share", timedelta(hours=2))
        share.view_count += 1
        share.last_viewed_at = utcnow()
        db.commit()
        payload = _media_payload(export, token, access)
        payload.update({"locked": False, "has_password": False, "access": access, "expires_at": share.expires_at})
        return payload


@router.post("/public/shares/{token}/unlock")
def unlock_share(token: str, payload: ShareUnlock, request: Request):
    ip = request.client.host if request.client else "anon"
    enforce_rate_limit(f"share-unlock:{ip}", 10)
    from ..database import session_scope

    with session_scope() as db:
        share, export = _load_share(db, token)
        if share.password_hash and not verify_password(payload.password, share.password_hash):
            raise HTTPException(status_code=403, detail="That password is incorrect")
        access = create_token(share.id, "share", timedelta(hours=2))
        share.view_count += 1
        share.last_viewed_at = utcnow()
        db.commit()
        body = _media_payload(export, token, access)
        body.update({
            "locked": False,
            "has_password": bool(share.password_hash),
            "access": access,
            "expires_at": share.expires_at,
        })
        return body


def _serve_public(
    token: str,
    request: Request,
    access: str | None = None,
    password: str | None = None,
    download: bool = False,
    thumbnail: bool = False,
):
    from ..database import session_scope

    with session_scope() as db:
        share, export = _load_share(db, token)
        _authorize(share, access, password)
        key = export.thumbnail_key if thumbnail else export.storage_key
        if not key:
            raise HTTPException(status_code=404, detail="No preview image is available")
        filename = export.filename if not thumbnail else None
        return serve_key(request, key, filename=filename, inline=not download)


@router.get("/public/shares/{token}/media")
def public_media(
    token: str,
    request: Request,
    access: str | None = Query(default=None),
    password: str | None = Query(default=None),
):
    return _serve_public(token, request, access=access, password=password)


@router.get("/public/shares/{token}/download")
def public_download(
    token: str,
    request: Request,
    access: str | None = Query(default=None),
    password: str | None = Query(default=None),
):
    return _serve_public(token, request, access=access, password=password, download=True)


@router.get("/public/shares/{token}/thumbnail")
def public_thumbnail(
    token: str,
    request: Request,
    access: str | None = Query(default=None),
    password: str | None = Query(default=None),
):
    return _serve_public(token, request, access=access, password=password, thumbnail=True)