"""Request authentication, workspace scoping and rate limiting."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import ApiKey, AuditLog, Membership, Notification, User, Workspace
from .security import decode_token, hash_api_key

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}


@dataclass
class RequestContext:
    user: User
    workspace: Workspace
    role: str
    db: Session
    api_key_id: str | None = None
    ip_address: str = ""

    def require(self, minimum: str) -> None:
        if ROLE_RANK.get(self.role, 0) < ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires the {minimum} role or higher.",
            )


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> User:
    token = credentials.credentials if credentials else None
    if not token and x_api_key:
        token = x_api_key
    if not token:
        token = request.cookies.get(settings.session_cookie)
    if not token:
        raise _unauthorized()

    if token.startswith("fk_") or (x_api_key and token == x_api_key):
        record = db.scalar(select(ApiKey).where(ApiKey.prefix == _key_prefix(token)))
        if not record or record.revoked_at is not None:
            raise _unauthorized("Invalid API key")
        if hash_api_key(token) != record.key_hash:
            raise _unauthorized("Invalid API key")
        user = db.get(User, record.user_id)
        if not user or not user.is_active:
            raise _unauthorized("Account inactive")
        record.last_used_at = datetime.now(timezone.utc)
        db.commit()
        request.state.api_key_id = record.id
        request.state.api_key_workspace = record.workspace_id
        return user

    payload = decode_token(token, "access")
    if not payload:
        raise _unauthorized("Session expired")
    user = db.get(User, payload.get("sub", ""))
    if not user or not user.is_active:
        raise _unauthorized("Account inactive")
    return user


def _key_prefix(token: str) -> str:
    parts = token.split("_")
    return parts[1] if len(parts) >= 3 else ""


def get_context(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> RequestContext:
    api_key_id = getattr(request.state, "api_key_id", None)
    forced_ws = getattr(request.state, "api_key_workspace", None)
    if forced_ws and x_workspace_id and forced_ws != x_workspace_id:
        raise HTTPException(status_code=403, detail="API key is scoped to another workspace")
    workspace_id = forced_ws or x_workspace_id

    membership = None
    if workspace_id:
        membership = db.scalar(
            select(Membership).where(
                Membership.workspace_id == workspace_id, Membership.user_id == user.id
            )
        )
        if not membership:
            raise HTTPException(status_code=403, detail="You are not a member of this workspace")
    else:
        membership = db.scalar(
            select(Membership)
            .where(Membership.user_id == user.id)
            .order_by(Membership.created_at.asc())
        )
        if membership:
            workspace_id = membership.workspace_id

    workspace = db.get(Workspace, workspace_id) if workspace_id else None
    if not workspace:
        raise HTTPException(status_code=409, detail="No workspace available. Create one first.")

    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else ""
    )
    request.state.user_id = user.id
    return RequestContext(
        user=user,
        workspace=workspace,
        role=membership.role if membership else "viewer",
        db=db,
        api_key_id=api_key_id,
        ip_address=ip,
    )


# --- Rate limiting --------------------------------------------------------

_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)
_redis_client = None
_redis_checked = False


def _get_redis():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    if settings.redis_url:
        try:
            import redis

            _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client


def enforce_rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    """Fixed-window limiter with a Redis backend and in-process fallback."""
    now = time.time()
    client = _get_redis()
    if client is not None:
        bucket = f"ratelimit:{key}:{int(now // window_seconds)}"
        try:
            count = client.incr(bucket)
            if count == 1:
                client.expire(bucket, window_seconds + 1)
            if int(count) > limit:
                raise HTTPException(status_code=429, detail="Too many requests. Slow down.")
            return
        except HTTPException:
            raise
        except Exception:
            pass  # fall through to memory limiter

    with _lock:
        bucket_mem = _buckets[key]
        cutoff = now - window_seconds
        while bucket_mem and bucket_mem[0] < cutoff:
            bucket_mem.popleft()
        if len(bucket_mem) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests. Slow down.")
        bucket_mem.append(now)


def rate_limit(kind: str, limit: int):
    """Dependency factory. Uses the authenticated user when available."""

    def _dep(request: Request) -> None:
        identity = getattr(request.state, "user_id", None)
        if not identity:
            forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            identity = forwarded or (request.client.host if request.client else "anon")
        enforce_rate_limit(f"{kind}:{identity}", limit)

    return _dep


# --- Audit + notifications ------------------------------------------------


def record_audit(
    db: Session,
    action: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
    target_type: str = "",
    target_id: str = "",
    ip_address: str = "",
    meta: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            meta=meta or {},
        )
    )


def notify(
    db: Session,
    workspace_id: str,
    user_id: str | None,
    title: str,
    body: str = "",
    kind: str = "info",
) -> None:
    db.add(
        Notification(
            workspace_id=workspace_id, user_id=user_id, type=kind, title=title, body=body
        )
    )
