"""System-wide settings (feature flags, business config)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from .base import BaseDocument


class SystemSetting(BaseDocument):
    key: str = Field(description="Unique setting key, e.g. 'commission_withdrawals_enabled'")
    value: Any
    description: Optional[str] = None
    updated_by_user_id: Optional[str] = None
