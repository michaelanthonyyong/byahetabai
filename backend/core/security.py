"""Cryptographic helpers: password hashing + JWT create/decode.

Notes
-----
* `bcrypt.gensalt(rounds=12)` is used for password hashing (matches Phase 1 seed).
* Access tokens carry ``sub``, ``role``, ``email``, ``exp``, ``type='access'``.
* Refresh tokens carry ``sub``, ``exp``, ``type='refresh'`` only.
* Both use HS256 with ``JWT_SECRET`` from the environment.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"


def _jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def _access_ttl_minutes() -> int:
    return int(os.environ.get("JWT_ACCESS_TTL_MIN", "60"))


def _refresh_ttl_days() -> int:
    return int(os.environ.get("JWT_REFRESH_TTL_DAYS", "7"))


# --- password ------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT -----------------------------------------------------------------

def create_access_token(user_id: str, email: str, role: str) -> tuple[str, datetime]:
    exp = datetime.now(timezone.utc) + timedelta(minutes=_access_ttl_minutes())
    payload = {"sub": user_id, "email": email, "role": role, "type": "access", "exp": exp}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM), exp


def create_refresh_token(user_id: str) -> tuple[str, datetime]:
    exp = datetime.now(timezone.utc) + timedelta(days=_refresh_ttl_days())
    payload = {"sub": user_id, "type": "refresh", "exp": exp}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM), exp


def decode_token(token: str, expected_type: Optional[str] = None) -> dict[str, Any]:
    payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# --- opaque tokens (invite / password-reset) -----------------------------

def new_opaque_token(nbytes: int = 32) -> str:
    """URL-safe random token to send in email/UI."""
    return secrets.token_urlsafe(nbytes)


def hash_opaque_token(token: str) -> str:
    """SHA-256 hash of an opaque token for at-rest storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
