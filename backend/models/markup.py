"""Per-agent, per-package retail markup (PHP per pax)."""
from __future__ import annotations

from decimal import Decimal

from bson.decimal128 import Decimal128
from pydantic import Field, field_serializer, field_validator

from .base import BaseDocument, money_from_bson, money_to_bson


class AgentPackageMarkup(BaseDocument):
    agent_id: str = Field(description="FK → agent_profiles.id")
    package_id: str = Field(description="FK → packages.id")
    markup_amount: Decimal = Field(description="Added on top of agent_cost, per pax")
    updated_by_user_id: str

    @field_validator("markup_amount", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return money_from_bson(v) if isinstance(v, Decimal128) else v

    @field_serializer("markup_amount")
    def _ser_money(self, v: Decimal) -> str:
        return str(v)

    def to_mongo(self) -> dict:
        doc = super().to_mongo()
        doc["markup_amount"] = money_to_bson(doc["markup_amount"])
        return doc
