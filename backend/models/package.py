"""Package (a bookable tour) + embedded Images / Inclusions / Exclusions.

Design notes
------------
* Images, inclusions and exclusions are naturally 1-to-many *within* a
  package, so they are embedded rather than kept in separate collections.
  They still have their own ``id`` (UUID) so we can reference or reorder
  them stably.
* Monetary fields (``guest_price``, ``agent_cost``, ``commission_amount``)
  use ``Decimal128`` on disk via ``money_to_bson``.
* ``guest_price`` is what the public website shows.
* ``agent_cost`` is what the agent's booking balance is debited by per pax.
* ``commission_amount`` is what the agent earns per pax on a confirmed booking.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import List, Optional

from bson.decimal128 import Decimal128
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from .base import BaseDocument, money_from_bson, money_to_bson


class PackageStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PackageImage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    url: str
    alt: Optional[str] = None
    is_cover: bool = False
    sort_order: int = 0


class PackageInclusion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    text: str
    sort_order: int = 0


class PackageExclusion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    text: str
    sort_order: int = 0


class Package(BaseDocument):
    slug: str = Field(description="URL-safe unique identifier")
    title: str
    destination_id: str = Field(description="FK → destinations.id")

    # Pricing (all PHP in V1).
    guest_price: Decimal = Field(description="Public price per pax")
    agent_cost: Decimal = Field(description="Agent booking-balance debit per pax")
    commission_amount: Decimal = Field(
        default=Decimal("0.00"),
        description="Commission earned per pax when a booking is confirmed",
    )
    currency: str = "PHP"

    # Trip attributes.
    duration_days: int = Field(ge=1)
    duration_nights: int = Field(ge=0)
    min_pax: int = Field(default=1, ge=1)
    max_pax: int = Field(default=20, ge=1)

    # Marketing copy.
    summary: Optional[str] = None
    highlights: Optional[str] = None
    itinerary: Optional[str] = None

    # Embedded 1-to-many.
    images: List[PackageImage] = Field(default_factory=list)
    inclusions: List[PackageInclusion] = Field(default_factory=list)
    exclusions: List[PackageExclusion] = Field(default_factory=list)

    status: PackageStatus = PackageStatus.DRAFT
    is_featured: bool = False

    @field_validator("guest_price", "agent_cost", "commission_amount", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return money_from_bson(v) if isinstance(v, Decimal128) else v

    @field_serializer("guest_price", "agent_cost", "commission_amount")
    def _ser_money(self, v: Decimal) -> str:
        return str(v)

    def to_mongo(self) -> dict:
        doc = super().to_mongo()
        for k in ("guest_price", "agent_cost", "commission_amount"):
            if doc.get(k) is not None:
                doc[k] = money_to_bson(doc[k])
        return doc
