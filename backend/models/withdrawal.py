"""Commission withdrawal request — gated by ``system_settings`` flag."""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from bson.decimal128 import Decimal128
from pydantic import Field, field_serializer, field_validator

from .base import BaseDocument, money_from_bson, money_to_bson


class WithdrawalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CommissionWithdrawal(BaseDocument):
    agent_id: str = Field(description="FK → agent_profiles.id (requester)")
    amount: Decimal
    currency: str = "PHP"

    payout_method: Optional[str] = Field(
        default=None, description="Free-text description of the real-world payout method"
    )
    payout_reference: Optional[str] = None
    note: Optional[str] = None

    status: WithdrawalStatus = WithdrawalStatus.PENDING
    decided_by_user_id: Optional[str] = None
    decided_at: Optional[str] = None
    decision_note: Optional[str] = None
    transaction_id: Optional[str] = Field(
        default=None, description="FK → financial_transactions.id created on approval"
    )

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return money_from_bson(v) if isinstance(v, Decimal128) else v

    @field_serializer("amount")
    def _ser_money(self, v: Decimal) -> str:
        return str(v)

    def to_mongo(self) -> dict:
        doc = super().to_mongo()
        if doc.get("amount") is not None:
            doc["amount"] = money_to_bson(doc["amount"])
        return doc
