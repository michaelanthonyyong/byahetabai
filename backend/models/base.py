"""Base model + money/time helpers shared by all domain documents."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from bson.decimal128 import Decimal128
from pydantic import BaseModel, ConfigDict, Field


def utc_now_iso() -> str:
    """UTC timestamp as ISO-8601 string (project-wide convention)."""
    return datetime.now(timezone.utc).isoformat()


def money_to_bson(value: Optional[Decimal | float | int | str]) -> Optional[Decimal128]:
    """Convert a monetary value to BSON Decimal128 for storage. None passes through."""
    if value is None:
        return None
    if isinstance(value, Decimal128):
        return value
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    # Quantize to 2 decimal places to keep the ledger tidy.
    value = value.quantize(Decimal("0.01"))
    return Decimal128(value)


def money_from_bson(value: Any) -> Optional[Decimal]:
    """Convert a stored Decimal128 back to Python Decimal."""
    if value is None:
        return None
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class BaseDocument(BaseModel):
    """Foundation for every persisted document.

    Conventions
    -----------
    * ``id`` is a UUID4 string and is also stored as Mongo ``_id`` for uniqueness.
    * ``created_at`` / ``updated_at`` are ISO-8601 UTC strings.
    * Never expose ``_id`` in API responses.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True, arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    def to_mongo(self) -> dict:
        """Serialise for insertion. Uses ``id`` as ``_id``."""
        doc = self.model_dump(mode="python")
        doc["_id"] = doc["id"]
        return doc

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        """Instantiate from a Mongo document. Returns ``None`` for missing docs."""
        if doc is None:
            return None
        data = dict(doc)
        data.pop("_id", None)
        return cls(**data)

    def touch(self) -> None:
        """Update the ``updated_at`` timestamp in place."""
        self.updated_at = utc_now_iso()
