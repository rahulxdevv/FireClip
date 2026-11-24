"""Workspace, membership and API key management."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import RequestContext, get_context, record_audit
from ..models import ApiKey, AuditLog, EmailToken, Membership, User, Workspace
from ..schemas import (
    ActivityOut,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    MemberAdd,
    MemberOut,
    WorkspaceCreate,
    WorkspaceSummary,
    WorkspaceUpdate,
)
from ..security import generate_api_key
from ..services.email import send_workspace_invite
from ..services.tokens import consume_email_token, issue_email_token, peek_email_token

router = APIRouter(prefix="/api", tags=["workspaces"])


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:50] or "workspace"
    return f"{base}-{secrets.token_hex(3)}"


@router.get("/workspaces", response_model=list[WorkspaceSummary])
def list_workspaces(
    user=Depends(get_context), db: Session = Depends(get_db)
):
    rows = db.execute(
        select(Membership, Workspace)
        .join(Workspace, Workspace.id == Membership.workspace_id)
        .where(Membership.user_id == user.user.id)
        .order_by(Membership.created_at)
    ).all()
    result = []
    for membership, workspace in rows:
        count = db.scalar(
            select(func.count()).select_from(Membership).where(Membership.workspace_id == workspace.id)
        ) or 0
        result.append(
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
    return result


@router.post("/workspaces", response_model=WorkspaceSummary, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, ctx: RequestContext = Depends(get_context)):
    workspace = Workspace(
        name=payload.name.strip(),
        slug=_slugify(payload.name),
        owner_id=ctx.user.id,
        monthly_clip_limit=ctx.workspace.monthly_clip_limit,
        monthly_render_minutes=ctx.workspace.monthly_render_minutes,
    )
    ctx.db.add(workspace)
    ctx.db.flush()
    ctx.db.add(Membership(workspace_id=workspace.id, user_id=ctx.user.id, role="owner"))
    record_audit(ctx.db, "workspace.create", workspace_id=workspace.id, user_id=ctx.user.id,
                 target_type="workspace", target_id=workspace.id, ip_address=ctx.ip_address)
    ctx.db.commit()
    return WorkspaceSummary(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        plan=workspace.plan,
        monthly_clip_limit=workspace.monthly_clip_limit,
        monthly_render_minutes=workspace.monthly_render_minutes,
        created_at=workspace.created_at,
        role="owner",
        member_count=1,
    )


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceSummary)
def update_workspace(workspace_id: str, payload: WorkspaceUpdate, ctx: RequestContext = Depends(get_context)):
    if workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=403, detail="Switch to this workspace first")
    ctx.require("admin")
    if payload.name:
        ctx.workspace.name = payload.name.strip()
    record_audit(ctx.db, "workspace.update", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="workspace", target_id=ctx.workspace.id, ip_address=ctx.ip_address)
    ctx.db.commit()
    count = ctx.db.scalar(
        select(func.count()).select_from(Membership).where(Membership.workspace_id == ctx.workspace.id)
    ) or 0
    return WorkspaceSummary(
        id=ctx.workspace.id,
        name=ctx.workspace.name,
        slug=ctx.workspace.slug,
        plan=ctx.workspace.plan,
        monthly_clip_limit=ctx.workspace.monthly_clip_limit,
        monthly_render_minutes=ctx.workspace.monthly_render_minutes,
        created_at=ctx.workspace.created_at,
        role=ctx.role,
        member_count=count,
    )


@router.get("/workspaces/{workspace_id}/members", response_model=list[MemberOut])
def list_members(workspace_id: str, ctx: RequestContext = Depends(get_context)):
    if workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=403, detail="Switch to this workspace first")
    rows = ctx.db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(Membership.created_at)
    ).all()
    return [
        MemberOut(
            id=membership.id,
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=membership.role,
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]


@router.post("/workspaces/{workspace_id}/members", status_code=201)
def add_member(workspace_id: str, payload: MemberAdd, ctx: RequestContext = Depends(get_context)):
    if workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=403, detail="Switch to this workspace first")
    ctx.require("admin")
    user = ctx.db.scalar(select(User).where(func.lower(User.email) == payload.email.lower().strip()))
    if not user:
        # Invite the address instead of failing: the link works when they sign up.
        return _send_invite(
            ctx,
            email=payload.email.lower().strip(),
            role=payload.role,
            workspace_id=workspace_id,
            inviter=ctx.user.name,
            workspace_name=ctx.workspace.name,
        )
    existing = ctx.db.scalar(
        select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user.id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="That person is already a member")
    membership = Membership(workspace_id=workspace_id, user_id=user.id, role=payload.role)
    ctx.db.add(membership)
    record_audit(ctx.db, "workspace.member_add", workspace_id=workspace_id, user_id=ctx.user.id,
                 target_type="user", target_id=user.id, ip_address=ctx.ip_address,
                 meta={"role": payload.role})
    ctx.db.commit()
    return MemberOut(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.patch("/workspaces/{workspace_id}/members/{member_id}", response_model=MemberOut)
def update_member(workspace_id: str, member_id: str, payload: MemberAdd, ctx: RequestContext = Depends(get_context)):
    if workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=403, detail="Switch to this workspace first")
    ctx.require("admin")
    membership = ctx.db.get(Membership, member_id)
    if not membership or membership.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="The workspace owner role cannot be changed")
    membership.role = payload.role
    ctx.db.commit()
    user = ctx.db.get(User, membership.user_id)
    return MemberOut(
        id=membership.id,
        user_id=membership.user_id,
        email=user.email if user else "",
        name=user.name if user else "",
        role=membership.role,
        created_at=membership.created_at,
    )


@router.delete("/workspaces/{workspace_id}/members/{member_id}", status_code=204)
def remove_member(workspace_id: str, member_id: str, ctx: RequestContext = Depends(get_context)):
    if workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=403, detail="Switch to this workspace first")
    ctx.require("admin")
    membership = ctx.db.get(Membership, member_id)
    if not membership or membership.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="The workspace owner cannot be removed")
    ctx.db.delete(membership)
    ctx.db.commit()


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(ctx: RequestContext = Depends(get_context)):
    rows = ctx.db.scalars(
        select(ApiKey)
        .where(ApiKey.workspace_id == ctx.workspace.id, ApiKey.user_id == ctx.user.id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(rows)


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
def create_api_key(payload: ApiKeyCreate, ctx: RequestContext = Depends(get_context)):
    ctx.require("editor")
    full, prefix, key_hash = generate_api_key()
    key = ApiKey(
        user_id=ctx.user.id,
        workspace_id=ctx.workspace.id,
        name=payload.name.strip(),
        prefix=prefix,
        key_hash=key_hash,
    )
    ctx.db.add(key)
    record_audit(ctx.db, "api_key.create", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="api_key", target_id=key.id, ip_address=ctx.ip_address)
    ctx.db.commit()
    return ApiKeyCreated(
        id=key.id, name=key.name, prefix=key.prefix, created_at=key.created_at,
        last_used_at=None, revoked_at=None, key=full,
    )


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(key_id: str, ctx: RequestContext = Depends(get_context)):
    key = ctx.db.get(ApiKey, key_id)
    if not key or key.workspace_id != ctx.workspace.id or key.user_id != ctx.user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    from datetime import datetime, timezone

    key.revoked_at = datetime.now(timezone.utc)
    record_audit(ctx.db, "api_key.revoke", workspace_id=ctx.workspace.id, user_id=ctx.user.id,
                 target_type="api_key", target_id=key.id, ip_address=ctx.ip_address)
    ctx.db.commit()


@router.get("/audit-logs", response_model=list[ActivityOut])
def audit_logs(limit: int = 50, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    limit = max(1, min(200, limit))
    rows = ctx.db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.workspace_id == ctx.workspace.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        ActivityOut(
            id=log.id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            user_email=email,
            created_at=log.created_at,
            meta=log.meta or {},
        )
        for log, email in rows
    ]

def _pending_invites(db: Session, workspace_id: str) -> list[EmailToken]:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(EmailToken)
        .where(
            EmailToken.workspace_id == workspace_id,
            EmailToken.kind == "invite",
            EmailToken.used_at.is_(None),
        )
        .order_by(EmailToken.created_at.desc())
    ).all()
    live = []
    for row in rows:
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires > now:
            live.append(row)
    return live


def _send_invite(
    ctx: RequestContext,
    *,
    email: str,
    role: str,
    workspace_id: str,
    inviter: str,
    workspace_name: str,
) -> dict:
    existing = ctx.db.scalar(
        select(EmailToken).where(
            EmailToken.workspace_id == workspace_id,
            EmailToken.kind == "invite",
            EmailToken.email == email,
            EmailToken.used_at.is_(None),
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="An invitation is already pending for that email")
    raw = issue_email_token(
        ctx.db,
        email=email,
        kind="invite",
        workspace_id=workspace_id,
        role=role,
        expires_delta=timedelta(days=settings.invite_expiry_days),
    )
    record_audit(
        ctx.db,
        "workspace.invite",
        workspace_id=workspace_id,
        user_id=ctx.user.id,
        target_type="email",
        target_id=email,
        ip_address=ctx.ip_address,
        meta={"role": role},
    )
    ctx.db.commit()
    sent = send_workspace_invite(email, inviter, workspace_name, role, raw)
    return {
        "status": "invited",
        "email": email,
        "role": role,
        "email_sent": sent,
        "dev_link": (
            f"{settings.frontend_url.rstrip('/')}/invite/{raw}"
            if settings.debug and not settings.email_configured
            else None
        ),
    }


@router.get("/workspaces/{workspace_id}/invites")
def list_invites(workspace_id: str, ctx: RequestContext = Depends(get_context)):
    if workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=403, detail="Switch to this workspace first")
    ctx.require("admin")
    return [
        {
            "id": row.id,
            "email": row.email,
            "role": row.role,
            "expires_at": row.expires_at,
            "created_at": row.created_at,
        }
        for row in _pending_invites(ctx.db, workspace_id)
    ]


@router.post("/workspaces/{workspace_id}/invites", status_code=201)
def create_invite(workspace_id: str, payload: MemberAdd, ctx: RequestContext = Depends(get_context)):
    if workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=403, detail="Switch to this workspace first")
    ctx.require("admin")
    email = payload.email.lower().strip()
    user = ctx.db.scalar(select(User).where(func.lower(User.email) == email))
    if user:
        membership = ctx.db.scalar(
            select(Membership).where(
                Membership.workspace_id == workspace_id, Membership.user_id == user.id
            )
        )
        if membership:
            raise HTTPException(status_code=409, detail="That person is already a member")
        ctx.db.add(Membership(workspace_id=workspace_id, user_id=user.id, role=payload.role))
        record_audit(
            ctx.db,
            "workspace.member_add",
            workspace_id=workspace_id,
            user_id=ctx.user.id,
            target_type="user",
            target_id=user.id,
            ip_address=ctx.ip_address,
            meta={"role": payload.role},
        )
        ctx.db.commit()
        return {"status": "member_added", "email": user.email, "role": payload.role}
    return _send_invite(
        ctx,
        email=email,
        role=payload.role,
        workspace_id=workspace_id,
        inviter=ctx.user.name,
        workspace_name=ctx.workspace.name,
    )


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}", status_code=204)
def revoke_invite(workspace_id: str, invite_id: str, ctx: RequestContext = Depends(get_context)):
    if workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=403, detail="Switch to this workspace first")
    ctx.require("admin")
    token = ctx.db.get(EmailToken, invite_id)
    if not token or token.workspace_id != workspace_id or token.kind != "invite":
        raise HTTPException(status_code=404, detail="Invitation not found")
    token.used_at = datetime.now(timezone.utc)
    record_audit(
        ctx.db,
        "workspace.invite_revoke",
        workspace_id=workspace_id,
        user_id=ctx.user.id,
        target_type="email",
        target_id=token.email,
        ip_address=ctx.ip_address,
    )
    ctx.db.commit()


@router.post("/workspaces/invites/{token}/accept", response_model=WorkspaceSummary)
def accept_invite(token: str, ctx: RequestContext = Depends(get_context)):
    invite = consume_email_token(ctx.db, token, "invite")
    if not invite or not invite.workspace_id:
        raise HTTPException(status_code=400, detail="This invitation is invalid or has expired")
    workspace = ctx.db.get(Workspace, invite.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="That workspace no longer exists")
    if invite.email.lower() != ctx.user.email.lower():
        raise HTTPException(status_code=403, detail="This invitation was issued to a different email address")
    membership = ctx.db.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace.id, Membership.user_id == ctx.user.id
        )
    )
    if not membership:
        membership = Membership(workspace_id=workspace.id, user_id=ctx.user.id, role=invite.role)
        ctx.db.add(membership)
    record_audit(
        ctx.db,
        "workspace.invite_accept",
        workspace_id=workspace.id,
        user_id=ctx.user.id,
        target_type="user",
        target_id=ctx.user.id,
        ip_address=ctx.ip_address,
    )
    ctx.db.commit()
    count = ctx.db.scalar(
        select(func.count()).select_from(Membership).where(Membership.workspace_id == workspace.id)
    ) or 0
    return WorkspaceSummary(
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