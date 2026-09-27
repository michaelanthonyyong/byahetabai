"""Customer — a guest managed by a single agent.

Agent isolation invariant: every customer belongs to exactly one agent
(``agent_id``) and is only visible via that agent's identity.
"""
from __future__ import annotations

from typing import Optional

from pydantic import EmailStr, Field

from .base import BaseDocument


class Customer(BaseDocument):
    agent_id: str = Field(description="FK → agent_profiles.id (owner)")
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True
