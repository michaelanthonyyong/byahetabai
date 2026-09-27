"""Commission ledger row — one entry per accrual event.

Distinct from ``financial_transactions``: this collection tracks the
lifecycle of an individual commission (accrued → paid or reversed).  The
matching financial_transactions row is created at the same time in a
single Mongo transaction.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from bson.decimal128 import Decimal128
from pydantic import Field, field_serializer, field_validator

from .base import BaseDocument, money_from_bson, money_to_bson


class CommissionStatus(str, Enum):
    ACCRUED = "accrued"
    PAID = "paid"
    REVERSED = "reversed"


class Commission(BaseDocument):
    agent_id: str = Field(description="FK → agent_profiles.id")
    booking_id: str = Field(description="FK → bookings.id (source)")
    amount: Decimal
    currency: str = "PHP"

    status: CommissionStatus = CommissionStatus.ACCRUED

    accrual_transaction_id: Optional[str] = Field(
        default=None, description="FK → financial_transactions.id (COMMISSION_ACCRUAL row)"
    )
    withdrawal_id: Optional[str] = Field(
        default=None, description="FK → commission_withdrawals.id when included in a payout"
    )
    reversal_transaction_id: Optional[str] = None
    note: Optional[str] = None

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
