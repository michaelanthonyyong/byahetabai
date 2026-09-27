"""Public catalogue endpoints for the marketing site.

Everything here is unauthenticated and read-only.  Whitelisting is strict:
``agent_cost`` and ``commission_amount`` are NEVER exposed.  Only
published packages are visible.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from bson.decimal128 import Decimal128
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from core.db import Collections, get_db
from models.base import money_from_bson, utc_now_iso

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["public"])


# --- serialisers (strict whitelist) -------------------------------------

def _destination_out(d: dict) -> dict:
    return {
        "id": d["_id"],
        "slug": d["slug"],
        "name": d["name"],
        "country": d["country"],
        "scope": d["scope"],
        "hero_image_url": d.get("hero_image_url"),
        "short_description": d.get("short_description"),
        "long_description": d.get("long_description"),
        "featured_on_home": bool(d.get("featured_on_home")),
    }


def _package_card(p: dict, destination: Optional[dict] = None) -> dict:
    """Compact shape used by grids.  Excludes agent_cost / commission."""
    cover = next(
        (img for img in p.get("images", []) if img.get("is_cover")),
        (p.get("images") or [{}])[0],
    )
    price = money_from_bson(p.get("guest_price")) if p.get("guest_price") is not None else None
    return {
        "id": p["_id"],
        "slug": p["slug"],
        "title": p["title"],
        "summary": p.get("summary"),
        "duration_days": p.get("duration_days"),
        "duration_nights": p.get("duration_nights"),
        "min_pax": p.get("min_pax"),
        "max_pax": p.get("max_pax"),
        "guest_price": str(price) if price is not None else None,
        "currency": p.get("currency", "PHP"),
        "cover_image_url": cover.get("url") if cover else None,
        "is_featured": bool(p.get("is_featured")),
        "destination": {
            "id": destination["_id"], "slug": destination["slug"],
            "name": destination["name"], "country": destination["country"],
            "scope": destination["scope"],
        } if destination else None,
    }


def _package_detail(p: dict, destination: Optional[dict] = None) -> dict:
    """Full detail — still no agent_cost / commission."""
    return {
        **_package_card(p, destination),
        "highlights": p.get("highlights"),
        "itinerary": p.get("itinerary"),
        "images": [
            {"id": i.get("id"), "url": i.get("url"), "alt": i.get("alt"), "is_cover": bool(i.get("is_cover"))}
            for i in sorted(p.get("images", []), key=lambda x: x.get("sort_order", 0))
        ],
        "inclusions": [
            {"id": x.get("id"), "text": x.get("text")}
            for x in sorted(p.get("inclusions", []), key=lambda x: x.get("sort_order", 0))
        ],
        "exclusions": [
            {"id": x.get("id"), "text": x.get("text")}
            for x in sorted(p.get("exclusions", []), key=lambda x: x.get("sort_order", 0))
        ],
    }


# --- destinations --------------------------------------------------------

@router.get("/destinations")
async def list_destinations(featured: Optional[bool] = None):
    db = get_db()
    query: dict = {"is_active": True}
    if featured is not None:
        query["featured_on_home"] = featured
    rows = await db[Collections.DESTINATIONS].find(query).sort("name", 1).to_list(length=200)
    return {"destinations": [_destination_out(d) for d in rows]}


@router.get("/destinations/{slug}")
async def get_destination(slug: str):
    db = get_db()
    dest = await db[Collections.DESTINATIONS].find_one({"slug": slug, "is_active": True})
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    pkg_rows = await db[Collections.PACKAGES].find(
        {"destination_id": dest["_id"], "status": "published"}
    ).sort([("is_featured", -1), ("title", 1)]).to_list(length=100)

    return {
        "destination": _destination_out(dest),
        "packages": [_package_card(p, dest) for p in pkg_rows],
    }


# --- packages ------------------------------------------------------------

@router.get("/packages")
async def list_packages(
    scope: Optional[str] = Query(default=None, pattern="^(domestic|international)$"),
    destination: Optional[str] = Query(default=None, description="destination slug"),
    q: Optional[str] = Query(default=None, description="free-text search"),
    featured: Optional[bool] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=60),
):
    db = get_db()
    dest_map: dict[str, dict] = {}

    # Optional destination filters resolved to a set of destination ids.
    dest_ids: Optional[set[str]] = None
    if scope or destination:
        dq: dict = {"is_active": True}
        if scope:
            dq["scope"] = scope
        if destination:
            dq["slug"] = destination
        async for d in db[Collections.DESTINATIONS].find(dq):
            dest_map[d["_id"]] = d
        dest_ids = set(dest_map.keys())
        if not dest_ids:
            return {"packages": [], "page": page, "page_size": page_size, "total": 0}

    pquery: dict = {"status": "published"}
    if dest_ids is not None:
        pquery["destination_id"] = {"$in": list(dest_ids)}
    if featured is not None:
        pquery["is_featured"] = featured
    if q:
        # Simple case-insensitive title / summary search.
        pattern = re.escape(q.strip())
        pquery["$or"] = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"summary": {"$regex": pattern, "$options": "i"}},
        ]

    total = await db[Collections.PACKAGES].count_documents(pquery)
    cursor = (
        db[Collections.PACKAGES].find(pquery)
        .sort([("is_featured", -1), ("title", 1)])
        .skip((page - 1) * page_size).limit(page_size)
    )
    rows = await cursor.to_list(length=page_size)

    # Batch-load any destinations we haven't already seen.
    missing = {r["destination_id"] for r in rows} - set(dest_map.keys())
    if missing:
        async for d in db[Collections.DESTINATIONS].find({"_id": {"$in": list(missing)}}):
            dest_map[d["_id"]] = d

    return {
        "packages": [_package_card(p, dest_map.get(p["destination_id"])) for p in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/packages/{slug}")
async def get_package(slug: str):
    db = get_db()
    pkg = await db[Collections.PACKAGES].find_one({"slug": slug, "status": "published"})
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    dest = await db[Collections.DESTINATIONS].find_one({"_id": pkg["destination_id"]})
    return {"package": _package_detail(pkg, dest)}


# --- brand ---------------------------------------------------------------

@router.get("/brand")
async def get_brand():
    row = await get_db()[Collections.SETTINGS].find_one({"key": "brand"})
    return {"brand": (row or {}).get("value", {})}


# --- contact -------------------------------------------------------------

CONTACT_COLLECTION = "contact_messages"


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=40)
    subject: Optional[str] = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    package_slug: Optional[str] = Field(default=None, max_length=200)


@router.post("/contact")
async def submit_contact(payload: ContactIn, request: Request):
    """Store a guest contact-agent request.  No PII beyond what user typed."""
    doc = {
        **payload.model_dump(),
        "email": payload.email.lower(),
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "created_at": utc_now_iso(),
        "status": "new",
    }
    await get_db()[CONTACT_COLLECTION].insert_one(doc)
    return {"ok": True, "message": "Thanks — an agent will be in touch soon."}
