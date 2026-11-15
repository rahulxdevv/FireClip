"""Password hashing, JWT sessions, API keys and secret encryption."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings

API_KEY_PREFIX = "fk"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(
    subject: str,
    token_type: str = "access",
    expires_delta: timedelta | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = (
            timedelta(minutes=settings.access_token_minutes)
            if token_type == "access"
            else timedelta(days=settings.refresh_token_days)
        )
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": secrets.token_hex(8),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


# --- API keys -------------------------------------------------------------


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, sha256_hash). The full key is shown once."""
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    full = f"{API_KEY_PREFIX}_{prefix}_{secret}"
    return full, prefix, hashlib.sha256(full.encode("utf-8")).hexdigest()


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


def verify_api_key(full_key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(full_key), stored_hash)


# --- Encrypted provider/OAuth secrets ------------------------------------


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    aes = AESGCM(settings.secrets_encryption_key)
    nonce = secrets.token_bytes(12)
    ciphertext = aes.encrypt(nonce, value.encode("utf-8"), b"fireclip")
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        nonce, ciphertext = raw[:12], raw[12:]
        return AESGCM(settings.secrets_encryption_key).decrypt(nonce, ciphertext, b"fireclip").decode("utf-8")
    except Exception:
        return ""


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}…{value[-4:]}"
