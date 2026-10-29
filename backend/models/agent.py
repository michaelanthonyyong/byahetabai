"""Agent profile + the two financial accounts (booking / commission).

The two ``AgentAccount`` sub-documents are the *cached* balance projections.
Ground truth lives in ``financial_transactions``; balances are recomputable
by summing signed transaction amounts.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from bson.decimal128 import Decimal128
from pydantic import Field, field_serializer, field_validator

from .base import BaseDocument, money_from_bson, money_to_bson


class AgentStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    DISABLED = "disabled"


class AgentAccount(BaseDocument):
    """Financial sub-account embedded on an ``AgentProfile``.

    Two are always present per agent:

    * ``booking`` — funds available to spend on bookings.
    * ``commission`` — earned commissions available to withdraw.
    """

    kind: str = Field(description="'booking' | 'commission'")
    balance: Decimal = Decimal("0.00")
    currency: str = "PHP"

    @field_validator("balance", mode="before")
    @classmethod
    def _coerce_balance(cls, v):
        return money_from_bson(v) if isinstance(v, Decimal128) else v

    @field_serializer("balance")
    def _ser_balance(self, v: Decimal) -> str:
        return str(v)


class AgentProfile(BaseDocument):
    """Public + operational profile for a role=agent user."""

    user_id: str = Field(description="FK → users.id (1:1)")
    display_name: str
    agency_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: AgentStatus = AgentStatus.INVITED

    # Agent-controlled branding for customer documents and the portal.
    business_name: Optional[str] = None
    brand_color: Optional[str] = Field(default=None, description="#RRGGBB used on documents and portal")
    logo_path: Optional[str] = None
    logo_content_type: Optional[str] = None
    logo_updated_at: Optional[str] = None

    booking_account: AgentAccount = Field(default_factory=lambda: AgentAccount(kind="booking"))
    commission_account: AgentAccount = Field(
        default_factory=lambda: AgentAccount(kind="commission")
    )

    created_by_user_id: str = Field(description="admin user_id that created this agent")

    def to_mongo(self) -> dict:
        doc = super().to_mongo()
        for k in ("booking_account", "commission_account"):
            if doc.get(k) and doc[k].get("balance") is not None:
                doc[k]["balance"] = money_to_bson(doc[k]["balance"])
        return doc
