"""Append-only financial ledger.

Every balance-changing operation writes exactly one row here inside a Mongo
transaction with the entity + balance update + audit log.

Signed amounts:
    + TOP_UP, BOOKING_REFUND, COMMISSION_ACCRUAL, ADJUSTMENT_CREDIT
    - BOOKING_DEBIT, COMMISSION_WITHDRAWAL, ADJUSTMENT_DEBIT, COMMISSION_REVERSAL

The invariant SUM(signed amount, account=X) == agent.<X>_account.balance
is verified by the reconciliation task (Phase 8).
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from bson.decimal128 import Decimal128
from pydantic import Field, field_serializer, field_validator

from .base import BaseDocument, money_from_bson, money_to_bson


class TransactionType(str, Enum):
    TOP_UP = "TOP_UP"
    BOOKING_DEBIT = "BOOKING_DEBIT"
    BOOKING_REFUND = "BOOKING_REFUND"
    COMMISSION_ACCRUAL = "COMMISSION_ACCRUAL"
    COMMISSION_REVERSAL = "COMMISSION_REVERSAL"
    COMMISSION_WITHDRAWAL = "COMMISSION_WITHDRAWAL"
    ADJUSTMENT_CREDIT = "ADJUSTMENT_CREDIT"
    ADJUSTMENT_DEBIT = "ADJUSTMENT_DEBIT"


# Which account each type moves.
BOOKING_TYPES = {
    TransactionType.TOP_UP,
    TransactionType.BOOKING_DEBIT,
    TransactionType.BOOKING_REFUND,
    TransactionType.ADJUSTMENT_CREDIT,
    TransactionType.ADJUSTMENT_DEBIT,
}
COMMISSION_TYPES = {
    TransactionType.COMMISSION_ACCRUAL,
    TransactionType.COMMISSION_REVERSAL,
    TransactionType.COMMISSION_WITHDRAWAL,
}


class FinancialTransaction(BaseDocument):
    agent_id: str = Field(description="FK → agent_profiles.id")
    account_kind: str = Field(description="'booking' | 'commission'")
    type: TransactionType
    amount: Decimal = Field(description="Signed amount in currency units")
    balance_after: Decimal = Field(description="Snapshot of account balance after this entry")
    currency: str = "PHP"

    # Reference to the entity that caused this movement.
    ref_type: Optional[str] = Field(
        default=None, description="'fund_request' | 'booking' | 'commission_withdrawal' | 'adjustment'"
    )
    ref_id: Optional[str] = None
    idempotency_key: Optional[str] = Field(
        default=None, description="Unique per approval; prevents double-apply"
    )

    created_by_user_id: str = Field(description="user who caused this entry")
    note: Optional[str] = None

    @field_validator("amount", "balance_after", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return money_from_bson(v) if isinstance(v, Decimal128) else v

    @field_serializer("amount", "balance_after")
    def _ser_money(self, v: Decimal) -> str:
        return str(v)

    def to_mongo(self) -> dict:
        doc = super().to_mongo()
        for k in ("amount", "balance_after"):
            if doc.get(k) is not None:
                doc[k] = money_to_bson(doc[k])
        return doc
