"""Single-use email token helpers for verification, reset and invites."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EmailToken, utcnow


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_email_token(
    db: Session,
    *,
    email: str,
    kind: str,
    user_id: str | None = None,
    workspace_id: str | None = None,
    role: str = "editor",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a token and return the raw value (only stored hashed)."""
    raw = secrets.token_urlsafe(32)
    token = EmailToken(
        user_id=user_id,
        workspace_id=workspace_id,
        email=email.lower().strip(),
        kind=kind,
        token_hash=_digest(raw),
        role=role,
        expires_at=utcnow() + (expires_delta or timedelta(hours=48)),
    )
    db.add(token)
    db.flush()
    return raw


def consume_email_token(db: Session, raw: str, kind: str) -> EmailToken | None:
    """Return a live token and mark it used. Invalid/expired tokens return None."""
    if not raw:
        return None
    token = db.scalar(select(EmailToken).where(EmailToken.token_hash == _digest(raw)))
    if not token or token.kind != kind or token.used_at is not None:
        return None
    expires = token.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return None
    token.used_at = utcnow()
    return token


def peek_email_token(db: Session, raw: str, kind: str) -> EmailToken | None:
    if not raw:
        return None
    token = db.scalar(select(EmailToken).where(EmailToken.token_hash == _digest(raw)))
    if not token or token.kind != kind or token.used_at is not None:
        return None
    expires = token.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return None
    return token
