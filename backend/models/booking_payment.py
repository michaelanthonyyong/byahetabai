"""A customer payment recorded by the agent against one booking."""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from bson.decimal128 import Decimal128
from pydantic import Field, field_serializer, field_validator

from .base import BaseDocument, money_from_bson, money_to_bson


class PaymentMethod(str, Enum):
    CASH = "cash"
    GCASH = "gcash"
    BANK = "bank_transfer"
    CARD = "card"
    OTHER = "other"


class BookingPayment(BaseDocument):
    booking_id: str = Field(description="FK → bookings.id")
    agent_id: str = Field(description="FK → agent_profiles.id (owner)")
    amount: Decimal
    method: PaymentMethod
    paid_on: str = Field(description="ISO date the customer paid")
    reference: Optional[str] = None
    note: Optional[str] = None
    recorded_by_user_id: str

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return money_from_bson(v) if isinstance(v, Decimal128) else v

    @field_serializer("amount")
    def _ser_money(self, v: Decimal) -> str:
        return str(v)

    def to_mongo(self) -> dict:
        doc = super().to_mongo()
        doc["amount"] = money_to_bson(doc["amount"])
        return doc
