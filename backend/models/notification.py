"""In-portal notification.

External channels (email/SMS) are out of scope for V1.  This collection
only records in-portal messages that the target user sees in their bell menu.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from .base import BaseDocument


class NotificationChannel(str, Enum):
    IN_PORTAL = "in_portal"


class Notification(BaseDocument):
    user_id: str = Field(description="FK → users.id (recipient)")
    channel: NotificationChannel = NotificationChannel.IN_PORTAL
    kind: Optional[str] = Field(default=None, description="e.g. booking.confirmed, fund_request.approved")

    title: str
    body: str
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None

    is_read: bool = False
    read_at: Optional[str] = None
