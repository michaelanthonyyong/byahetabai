"""Audit log — one row per admin-sensitive action.

``before`` / ``after`` capture the shallow state changes.  The service
layer is responsible for writing these; there is no automatic hook.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from .base import BaseDocument


class AuditLog(BaseDocument):
    actor_user_id: str = Field(description="FK → users.id (who did it)")
    actor_role: str = Field(description="'admin' | 'agent' (snapshot at time of action)")

    action: str = Field(description="Verb, e.g. 'fund_request.approve'")
    target_type: str = Field(description="Entity type, e.g. 'fund_request'")
    target_id: str

    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None

    ip: Optional[str] = None
    user_agent: Optional[str] = None
    note: Optional[str] = None
