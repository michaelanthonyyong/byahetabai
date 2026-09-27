"""Auth-related persisted state.

* ``LoginAttempt`` — per ``ip:email`` counter with lockout window.
* ``PasswordResetToken`` — used for BOTH admin-issued password resets AND
  agent invitations.  ``kind`` disambiguates them.  Tokens are stored as
  a SHA-256 hash; the raw token is only shown once to the initiator.

The ``expires_at`` field is a native BSON datetime so we can attach a
Mongo TTL index (``expireAfterSeconds=0``) that auto-purges expired rows.
Everywhere else in the project we store timestamps as ISO strings; this
collection is the documented exception.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .base import BaseDocument, utc_now_iso


class TokenKind(str, Enum):
    INVITE = "invite"
    RESET = "reset"


class PasswordResetToken(BaseDocument):
    token_hash: str = Field(description="SHA-256 hex digest of the raw token")
    user_id: str = Field(description="FK → users.id")
    kind: TokenKind
    # BSON datetime so the TTL index fires.
    expires_at: datetime
    used_at: Optional[str] = None
    issued_by_user_id: Optional[str] = Field(
        default=None, description="admin user_id (None if self-service)"
    )

    def to_mongo(self) -> dict:
        doc = super().to_mongo()
        # keep expires_at as native datetime (BSON date) for TTL
        return doc


class LoginAttempt(BaseModel):
    """Rate-limit / lockout tracking. Not a BaseDocument (no id) — key is identifier."""

    model_config = ConfigDict(extra="ignore")
    identifier: str = Field(description="'{ip}:{email}' key")
    count: int = 0
    locked_until: Optional[str] = None
    updated_at: str = Field(default_factory=utc_now_iso)
