"""Password hashing + JWT."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt 72-byte limit
_BCRYPT_MAX_BYTES = 72


def _truncate(plain: str) -> bytes:
    """Encode + truncate to bcrypt's 72-byte limit."""
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """Hash a plain password using bcrypt."""
    return bcrypt.hashpw(_truncate(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against its hash."""
    try:
        return bcrypt.checkpw(_truncate(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_ttl_minutes)
    payload = {
        "sub": subject,
        "iat": now.timestamp(),
        "exp": expire.timestamp(),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """Create a signed JWT refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_refresh_token_ttl_minutes)
    payload = {
        "sub": subject,
        "iat": now.timestamp(),
        "exp": expire.timestamp(),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode + verify a JWT. Raises JWTError on invalid/expired."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


def verify_token_type(token: str, expected_type: str) -> dict:
    """Decode and verify the token type matches expected ('access' | 'refresh')."""
    payload = decode_token(token)
    if payload.get("type") != expected_type:
        raise JWTError(f"Expected token type {expected_type!r}, got {payload.get('type')!r}")
    return payload