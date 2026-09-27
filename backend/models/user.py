"""User (authentication identity) model.

Every human that can authenticate has a row here.  An ``agent`` role also
owns exactly one row in ``agent_profiles`` (see agent.py).  Master admins
do not have an agent profile.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import EmailStr, Field

from .base import BaseDocument


class UserRole(str, Enum):
    ADMIN = "admin"
    AGENT = "agent"


class UserStatus(str, Enum):
    INVITED = "invited"     # created by admin, has not set password yet
    ACTIVE = "active"
    DISABLED = "disabled"


class User(BaseDocument):
    email: EmailStr
    password_hash: str
    role: UserRole
    status: UserStatus = UserStatus.ACTIVE
    display_name: str
    last_login_at: Optional[str] = None
    # Only populated for role=agent; admin creates the account.
    created_by_user_id: Optional[str] = Field(
        default=None, description="user_id of the admin who provisioned this account"
    )
