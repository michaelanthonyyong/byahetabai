"""Public catalog: destination (a place packages are grouped under)."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from .base import BaseDocument


class DestinationScope(str, Enum):
    DOMESTIC = "domestic"
    INTERNATIONAL = "international"


class Destination(BaseDocument):
    slug: str = Field(description="URL-safe unique identifier, e.g. 'japan'")
    name: str
    country: str
    scope: DestinationScope
    hero_image_url: Optional[str] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    featured_on_home: bool = False
    is_active: bool = True
