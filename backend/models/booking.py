"""Booking + embedded Travelers + Status History.

Financial rule (documented, enforced by service layer in a later phase):
On create, the booking debits the agent's booking account by
``agent_cost * pax`` in a single Mongo transaction that also writes a
``financial_transactions`` row and an ``audit_logs`` row.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from bson.decimal128 import Decimal128
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from .base import BaseDocument, money_from_bson, money_to_bson, utc_now_iso


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class GuestPaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"


class BookingTraveler(BaseModel):
    """A single traveller on a booking.  Not necessarily a Customer row."""

    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    full_name: str
    is_lead: bool = False
    passport_no: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None  # ISO date


class BookingStatusHistoryEntry(BaseModel):
    """Immutable status-change record embedded on a booking."""

    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_status: Optional[BookingStatus] = None
    to_status: BookingStatus
    changed_by_user_id: str
    changed_at: str = Field(default_factory=utc_now_iso)
    note: Optional[str] = None


class Booking(BaseDocument):
    reference_code: str = Field(description="Human-friendly code, e.g. 'BTB-000123'")
    agent_id: str = Field(description="FK → agent_profiles.id (owner)")
    customer_id: str = Field(description="FK → customers.id")
    package_id: str = Field(description="FK → packages.id")

    # Snapshot of pricing at time of booking so later package edits do not
    # rewrite history.
    pax: int = Field(ge=1)
    unit_agent_cost: Decimal
    unit_guest_price: Decimal
    unit_commission_amount: Decimal
    total_agent_cost: Decimal
    total_guest_price: Decimal
    total_commission_amount: Decimal
    # Agent markup snapshot (agent-created bookings). Retail = agent cost + markup.
    unit_markup_amount: Optional[Decimal] = None
    total_markup_amount: Optional[Decimal] = None
    total_retail_price: Optional[Decimal] = None
    currency: str = "PHP"

    travel_start_date: Optional[str] = None  # ISO date
    travel_end_date: Optional[str] = None

    status: BookingStatus = BookingStatus.PENDING
    guest_payment_status: GuestPaymentStatus = GuestPaymentStatus.UNPAID

    travelers: List[BookingTraveler] = Field(default_factory=list)
    status_history: List[BookingStatusHistoryEntry] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator(
        "unit_agent_cost", "unit_guest_price", "unit_commission_amount",
        "total_agent_cost", "total_guest_price", "total_commission_amount",
        "unit_markup_amount", "total_markup_amount", "total_retail_price",
        mode="before",
    )
    @classmethod
    def _coerce_money(cls, v):
        return money_from_bson(v) if isinstance(v, Decimal128) else v

    @field_serializer(
        "unit_agent_cost", "unit_guest_price", "unit_commission_amount",
        "total_agent_cost", "total_guest_price", "total_commission_amount",
        "unit_markup_amount", "total_markup_amount", "total_retail_price",
    )
    def _ser_money(self, v: Optional[Decimal]) -> Optional[str]:
        return str(v) if v is not None else None

    def to_mongo(self) -> dict:
        doc = super().to_mongo()
        for k in (
            "unit_agent_cost", "unit_guest_price", "unit_commission_amount",
            "total_agent_cost", "total_guest_price", "total_commission_amount",
            "unit_markup_amount", "total_markup_amount", "total_retail_price",
        ):
            if doc.get(k) is not None:
                doc[k] = money_to_bson(doc[k])
        return doc
