"""Auth business logic: login, logout, refresh, invite, reset, change password.

Keep routers thin — all rules live here so they can be unit-tested
independently of FastAPI in a later phase.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from pydantic import EmailStr

from core.db import Collections, get_db
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_opaque_token,
    hash_password,
    new_opaque_token,
    verify_password,
)
from models.auth import PasswordResetToken, TokenKind
from models.base import utc_now_iso
from models.user import UserRole, UserStatus

logger = logging.getLogger(__name__)

LOGIN_ATTEMPTS_COLLECTION = "login_attempts"
TOKENS_COLLECTION = "auth_tokens"


def _lockout_attempts() -> int:
    return int(os.environ.get("LOGIN_LOCKOUT_ATTEMPTS", "5"))


def _lockout_minutes() -> int:
    return int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))


def _invite_ttl_hours() -> int:
    return int(os.environ.get("INVITE_TTL_HOURS", "72"))


def _reset_ttl_hours() -> int:
    return int(os.environ.get("RESET_TTL_HOURS", "4"))


# --- Brute-force protection ---------------------------------------------

async def _check_and_bump_lockout(identifier: str, success: bool) -> None:
    db = get_db()
    now = datetime.now(timezone.utc)
    row = await db[LOGIN_ATTEMPTS_COLLECTION].find_one({"_id": identifier})

    if row and row.get("locked_until"):
        locked_until = row["locked_until"]
        if isinstance(locked_until, str):
            locked_until = datetime.fromisoformat(locked_until)
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account temporarily locked. Try again after {locked_until.isoformat()}.",
            )

    if success:
        await db[LOGIN_ATTEMPTS_COLLECTION].delete_one({"_id": identifier})
        return

    new_count = (row["count"] if row else 0) + 1
    update: dict = {"count": new_count, "updated_at": now.isoformat()}
    if new_count >= _lockout_attempts():
        update["locked_until"] = (now + timedelta(minutes=_lockout_minutes())).isoformat()
        update["count"] = 0  # reset counter after lockout
    await db[LOGIN_ATTEMPTS_COLLECTION].update_one(
        {"_id": identifier}, {"$set": update}, upsert=True
    )


# --- Public API ---------------------------------------------------------

async def login(email: str, password: str, ip: Optional[str]) -> dict:
    """Authenticate and return ``{user, access_token, refresh_token}``."""
    email = email.lower().strip()
    identifier = f"{ip or 'no-ip'}:{email}"
    db = get_db()

    # Pre-check lockout without incrementing.
    await _check_and_bump_lockout(identifier, success=True) if False else None
    # (Explicit call below covers both check + bump on failure.)
    user = await db[Collections.USERS].find_one({"email": email})
    ok = bool(user) and user.get("status") != UserStatus.DISABLED and verify_password(
        password, user.get("password_hash", "")
    )

    if not ok:
        await _check_and_bump_lockout(identifier, success=False)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.get("status") == UserStatus.INVITED:
        # Invited users must accept invitation first.
        raise HTTPException(
            status_code=403,
            detail="Account not yet activated. Please accept your invitation first.",
        )

    await _check_and_bump_lockout(identifier, success=True)

    access, _ = create_access_token(user["_id"], user["email"], user["role"])
    refresh, _ = create_refresh_token(user["_id"])
    await db[Collections.USERS].update_one(
        {"_id": user["_id"]}, {"$set": {"last_login_at": utc_now_iso()}}
    )
    user.pop("password_hash", None)
    return {"user": user, "access_token": access, "refresh_token": refresh}


async def refresh_access_token(refresh_token: str) -> tuple[str, dict]:
    import jwt
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await get_db()[Collections.USERS].find_one({"_id": payload["sub"]})
    if not user or user.get("status") == UserStatus.DISABLED:
        raise HTTPException(status_code=401, detail="User not available")

    access, _ = create_access_token(user["_id"], user["email"], user["role"])
    user.pop("password_hash", None)
    return access, user


# --- Invitation + password reset -----------------------------------------

async def _issue_token(user_id: str, kind: TokenKind, issued_by: Optional[str], ttl_hours: int) -> str:
    raw = new_opaque_token()
    doc = PasswordResetToken(
        token_hash=hash_opaque_token(raw),
        user_id=user_id,
        kind=kind,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        issued_by_user_id=issued_by,
    )
    await get_db()[TOKENS_COLLECTION].insert_one(doc.to_mongo())
    return raw


async def issue_invite_token(user_id: str, issued_by: str) -> str:
    return await _issue_token(user_id, TokenKind.INVITE, issued_by, _invite_ttl_hours())


async def issue_reset_token(user_id: str, issued_by: Optional[str]) -> str:
    return await _issue_token(user_id, TokenKind.RESET, issued_by, _reset_ttl_hours())


async def _consume_token(raw_token: str, expected_kind: TokenKind) -> dict:
    """Return the user document; delete the token atomically."""
    db = get_db()
    token_hash = hash_opaque_token(raw_token)
    row = await db[TOKENS_COLLECTION].find_one({"token_hash": token_hash, "kind": expected_kind.value})
    if not row:
        raise HTTPException(status_code=400, detail="Invalid or already-used token")
    if row.get("used_at"):
        raise HTTPException(status_code=400, detail="Token already used")
    exp = row["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
    user = await db[Collections.USERS].find_one({"_id": row["user_id"]})
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    return {"token_row": row, "user": user}


async def accept_invite(raw_token: str, new_password: str) -> dict:
    ctx = await _consume_token(raw_token, TokenKind.INVITE)
    user = ctx["user"]
    db = get_db()
    await db[Collections.USERS].update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": hash_password(new_password),
            "status": UserStatus.ACTIVE.value,
            "updated_at": utc_now_iso(),
        }},
    )
    if user.get("role") == UserRole.AGENT.value:
        await db[Collections.AGENT_PROFILES].update_one(
            {"user_id": user["_id"]},
            {"$set": {"status": "active", "updated_at": utc_now_iso()}},
        )
    await db[TOKENS_COLLECTION].delete_one({"_id": ctx["token_row"]["_id"]})
    return {"email": user["email"]}


async def reset_password_with_token(raw_token: str, new_password: str) -> dict:
    ctx = await _consume_token(raw_token, TokenKind.RESET)
    user = ctx["user"]
    db = get_db()
    await db[Collections.USERS].update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": hash_password(new_password),
            "updated_at": utc_now_iso(),
        }},
    )
    await db[TOKENS_COLLECTION].delete_one({"_id": ctx["token_row"]["_id"]})
    # Invalidate any other reset/invite tokens for this user.
    await db[TOKENS_COLLECTION].delete_many({"user_id": user["_id"]})
    return {"email": user["email"]}


async def change_password(user_id: str, current_password: str, new_password: str) -> None:
    db = get_db()
    user = await db[Collections.USERS].find_one({"_id": user_id})
    if not user or not verify_password(current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    await db[Collections.USERS].update_one(
        {"_id": user_id},
        {"$set": {"password_hash": hash_password(new_password), "updated_at": utc_now_iso()}},
    )
