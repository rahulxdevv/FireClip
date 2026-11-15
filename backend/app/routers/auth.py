"""Authentication and session routes."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import RequestContext, enforce_rate_limit, get_context, get_current_user, record_audit
from ..models import Membership, User, Workspace
from ..schemas import (
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    RegisterRequest,
    SessionOut,
    UserOut,
    WorkspaceSummary,
)
from ..security import create_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:50] or "workspace"
    return f"{base}-{secrets.token_hex(3)}"


def _session_payload(db: Session, user: User, active: str | None = None) -> dict:
    memberships = db.execute(
        select(Membership, Workspace)
        .join(Workspace, Workspace.id == Membership.workspace_id)
        .where(Membership.user_id == user.id)
        .order_by(Membership.created_at)
    ).all()
    workspaces = []
    for membership, workspace in memberships:
        count = db.scalar(
            select(func.count()).select_from(Membership).where(Membership.workspace_id == workspace.id)
        ) or 0
        workspaces.append(
            WorkspaceSummary(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                plan=workspace.plan,
                monthly_clip_limit=workspace.monthly_clip_limit,
                monthly_render_minutes=workspace.monthly_render_minutes,
                created_at=workspace.created_at,
                role=membership.role,
                member_count=count,
            )
        )
    workspace_ids = {w.id for w in workspaces}
    return {
        "user": UserOut.model_validate(user),
        "workspaces": workspaces,
        "active_workspace_id": active if active in workspace_ids else (workspaces[0].id if workspaces else None),
    }


def _set_session_cookies(response: Response, user_id: str) -> None:
    access = create_token(user_id, "access")
    refresh = create_token(user_id, "refresh")
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(
        settings.session_cookie, access, max_age=settings.access_token_minutes * 60, **common
    )
    response.set_cookie(
        settings.refresh_cookie, refresh, max_age=settings.refresh_token_days * 86400, **common
    )


def _validate_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    allowed = set(settings.cors_origins) | {settings.frontend_url}
    if origin not in allowed:
        raise HTTPException(status_code=403, detail="Origin not allowed")


@router.post("/register", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _validate_origin(request)
    enforce_rate_limit(f"register:{request.client.host if request.client else 'anon'}", settings.rate_limit_auth_per_minute)
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="Registration is disabled on this instance")
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip() or email.split("@")[0],
    )
    db.add(user)
    db.flush()
    workspace_name = payload.workspace_name.strip() or f"{user.name}'s studio"
    workspace = Workspace(
        name=workspace_name,
        slug=_slugify(workspace_name),
        owner_id=user.id,
        monthly_clip_limit=settings.plan_clip_limit,
        monthly_render_minutes=settings.plan_render_minutes,
    )
    db.add(workspace)
    db.flush()
    db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
    record_audit(
        db, "auth.register", workspace_id=workspace.id, user_id=user.id,
        target_type="user", target_id=user.id,
        ip_address=request.client.host if request.client else "",
    )
    db.commit()
    _set_session_cookies(response, user.id)
    return _session_payload(db, user, workspace.id)


@router.post("/login", response_model=SessionOut)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _validate_origin(request)
    ip = request.client.host if request.client else "anon"
    enforce_rate_limit(f"login:{ip}", settings.rate_limit_auth_per_minute)
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower().strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        # Constant-ish response time and no account enumeration.
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been disabled")
    user.last_login_at = datetime.now(timezone.utc)
    record_audit(db, "auth.login", user_id=user.id, target_type="user", target_id=user.id, ip_address=ip)
    db.commit()
    _set_session_cookies(response, user.id)
    return _session_payload(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record_audit(db, "auth.logout", user_id=user.id, target_type="user", target_id=user.id)
    db.commit()
    response.delete_cookie(settings.session_cookie, path="/")
    response.delete_cookie(settings.refresh_cookie, path="/")


@router.post("/refresh", response_model=SessionOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(settings.refresh_cookie)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_token(token, "refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    user = db.get(User, payload.get("sub", ""))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account unavailable")
    _set_session_cookies(response, user.id)
    return _session_payload(db, user)


@router.get("/me", response_model=SessionOut)
def me(ctx: RequestContext = Depends(get_context)):
    return _session_payload(ctx.db, ctx.user, ctx.workspace.id)


@router.patch("/profile", response_model=UserOut)
def update_profile(payload: ProfileUpdate, ctx: RequestContext = Depends(get_context)):
    ctx.user.name = payload.name.strip()
    record_audit(ctx.db, "user.profile_update", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="user", target_id=ctx.user.id, ip_address=ctx.ip_address)
    ctx.db.commit()
    ctx.db.refresh(ctx.user)
    return ctx.user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: PasswordChange, response: Response, ctx: RequestContext = Depends(get_context)):
    if not verify_password(payload.current_password, ctx.user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    ctx.user.password_hash = hash_password(payload.new_password)
    record_audit(ctx.db, "user.password_change", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="user", target_id=ctx.user.id, ip_address=ctx.ip_address)
    ctx.db.commit()
    # Rotate the session so old cookies cannot be reused indefinitely.
    _set_session_cookies(response, ctx.user.id)
