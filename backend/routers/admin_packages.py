"""Admin CRUD for packages under /api/admin/packages."""
from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Any, List, Optional

from bson.decimal128 import Decimal128
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from core.db import Collections, get_db
from core.deps import require_role
from models.audit_log import AuditLog
from models.base import money_from_bson, money_to_bson, utc_now_iso
from models.package import Package, PackageExclusion, PackageImage, PackageInclusion, PackageStatus

router = APIRouter(prefix="/api/admin/packages", tags=["admin:packages"])
require_admin = require_role("admin")


# --- schemas -------------------------------------------------------------

class ImageIn(BaseModel):
    id: Optional[str] = None
    url: str = Field(min_length=5, max_length=800)
    alt: Optional[str] = Field(default=None, max_length=200)
    is_cover: bool = False
    sort_order: int = 0


class InclusionIn(BaseModel):
    id: Optional[str] = None
    text: str = Field(min_length=1, max_length=400)
    sort_order: int = 0


class ExclusionIn(BaseModel):
    id: Optional[str] = None
    text: str = Field(min_length=1, max_length=400)
    sort_order: int = 0


class PackageIn(BaseModel):
    slug: str = Field(min_length=2, max_length=120, pattern="^[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=200)
    destination_id: str
    guest_price: Decimal = Field(ge=0)
    agent_cost: Decimal = Field(ge=0)
    commission_amount: Decimal = Field(ge=0)
    duration_days: int = Field(ge=1, le=90)
    duration_nights: int = Field(ge=0, le=90)
    min_pax: int = Field(ge=1, default=1)
    max_pax: int = Field(ge=1, default=20)
    summary: Optional[str] = Field(default=None, max_length=800)
    highlights: Optional[str] = Field(default=None, max_length=4000)
    itinerary: Optional[str] = Field(default=None, max_length=20_000)
    images: List[ImageIn] = Field(default_factory=list)
    inclusions: List[InclusionIn] = Field(default_factory=list)
    exclusions: List[ExclusionIn] = Field(default_factory=list)
    is_featured: bool = False


class PackagePatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    destination_id: Optional[str] = None
    guest_price: Optional[Decimal] = Field(default=None, ge=0)
    agent_cost: Optional[Decimal] = Field(default=None, ge=0)
    commission_amount: Optional[Decimal] = Field(default=None, ge=0)
    duration_days: Optional[int] = Field(default=None, ge=1, le=90)
    duration_nights: Optional[int] = Field(default=None, ge=0, le=90)
    min_pax: Optional[int] = Field(default=None, ge=1)
    max_pax: Optional[int] = Field(default=None, ge=1)
    summary: Optional[str] = Field(default=None, max_length=800)
    highlights: Optional[str] = Field(default=None, max_length=4000)
    itinerary: Optional[str] = Field(default=None, max_length=20_000)
    images: Optional[List[ImageIn]] = None
    inclusions: Optional[List[InclusionIn]] = None
    exclusions: Optional[List[ExclusionIn]] = None
    is_featured: Optional[bool] = None


class StatusIn(BaseModel):
    status: str = Field(pattern="^(draft|published|archived)$")


def _out(p: dict) -> dict:
    return {
        "id": p["_id"],
        "slug": p["slug"],
        "title": p["title"],
        "destination_id": p["destination_id"],
        "guest_price": str(money_from_bson(p.get("guest_price"))) if p.get("guest_price") is not None else "0.00",
        "agent_cost": str(money_from_bson(p.get("agent_cost"))) if p.get("agent_cost") is not None else "0.00",
        "commission_amount": str(money_from_bson(p.get("commission_amount"))) if p.get("commission_amount") is not None else "0.00",
        "currency": p.get("currency", "PHP"),
        "duration_days": p.get("duration_days"),
        "duration_nights": p.get("duration_nights"),
        "min_pax": p.get("min_pax"),
        "max_pax": p.get("max_pax"),
        "summary": p.get("summary"),
        "highlights": p.get("highlights"),
        "itinerary": p.get("itinerary"),
        "images": p.get("images", []),
        "inclusions": p.get("inclusions", []),
        "exclusions": p.get("exclusions", []),
        "status": p.get("status", "draft"),
        "is_featured": bool(p.get("is_featured")),
        "created_at": p["created_at"],
        "updated_at": p.get("updated_at"),
    }


def _normalise_children(items: list, ChildModel) -> list:
    """Assign UUIDs to new rows, keep incoming ones as-is."""
    out = []
    for it in items:
        d = it.model_dump() if hasattr(it, "model_dump") else dict(it)
        if not d.get("id"):
            d["id"] = str(uuid.uuid4())
        out.append(ChildModel(**d).model_dump())
    return out


def _ensure_single_cover(images: list) -> list:
    """If none are marked cover, promote the first; if many, keep only the first."""
    seen_cover = False
    for img in images:
        if img.get("is_cover"):
            if seen_cover:
                img["is_cover"] = False
            else:
                seen_cover = True
    if not seen_cover and images:
        images[0]["is_cover"] = True
    return images


async def _audit(admin, action, target_id, before, after, request):
    await get_db()[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=admin["_id"], actor_role="admin",
            action=action, target_type="package", target_id=target_id,
            before=before, after=after,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        ).to_mongo()
    )


# --- endpoints -----------------------------------------------------------

@router.get("")
async def list_packages(
    admin: dict = Depends(require_admin),
    status: Optional[str] = Query(default=None, pattern="^(draft|published|archived)$"),
    destination_id: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    db = get_db()
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if destination_id:
        query["destination_id"] = destination_id
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"title": rx}, {"slug": rx}, {"summary": rx}]

    total = await db[Collections.PACKAGES].count_documents(query)
    rows = await (
        db[Collections.PACKAGES].find(query).sort([("is_featured", -1), ("title", 1)])
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )

    # attach destination info + booking counts
    dest_ids = {r["destination_id"] for r in rows}
    dests = {d["_id"]: d async for d in db[Collections.DESTINATIONS].find({"_id": {"$in": list(dest_ids)}})}
    pkg_ids = [r["_id"] for r in rows]
    booking_counts: dict[str, int] = {}
    if pkg_ids:
        async for agg in db[Collections.BOOKINGS].aggregate([
            {"$match": {"package_id": {"$in": pkg_ids}}},
            {"$group": {"_id": "$package_id", "n": {"$sum": 1}}},
        ]):
            booking_counts[agg["_id"]] = agg["n"]

    def one(r):
        base = _out(r)
        d = dests.get(r["destination_id"])
        base["destination"] = (
            {"id": d["_id"], "slug": d["slug"], "name": d["name"], "scope": d["scope"]} if d else None
        )
        base["booking_count"] = booking_counts.get(r["_id"], 0)
        # strip embedded arrays from the list view — kept for detail only
        base.pop("images", None); base.pop("inclusions", None); base.pop("exclusions", None)
        base.pop("highlights", None); base.pop("itinerary", None)
        return base

    return {
        "packages": [one(r) for r in rows],
        "page": page, "page_size": page_size, "total": total,
    }


@router.get("/{package_id}")
async def get_package(package_id: str, admin: dict = Depends(require_admin)):
    db = get_db()
    p = await db[Collections.PACKAGES].find_one({"_id": package_id})
    if not p:
        raise HTTPException(status_code=404, detail="Package not found")
    d = await db[Collections.DESTINATIONS].find_one({"_id": p["destination_id"]})
    base = _out(p)
    base["destination"] = (
        {"id": d["_id"], "slug": d["slug"], "name": d["name"], "scope": d["scope"]} if d else None
    )
    return {"package": base}


@router.post("", status_code=201)
async def create_package(payload: PackageIn, request: Request, admin: dict = Depends(require_admin)):
    db = get_db()
    if await db[Collections.PACKAGES].find_one({"slug": payload.slug}):
        raise HTTPException(status_code=409, detail="A package with this slug already exists")
    if not await db[Collections.DESTINATIONS].find_one({"_id": payload.destination_id}):
        raise HTTPException(status_code=400, detail="destination_id does not exist")
    if payload.max_pax < payload.min_pax:
        raise HTTPException(status_code=400, detail="max_pax must be >= min_pax")

    data = payload.model_dump()
    data["images"] = _ensure_single_cover(_normalise_children(payload.images, PackageImage))
    data["inclusions"] = _normalise_children(payload.inclusions, PackageInclusion)
    data["exclusions"] = _normalise_children(payload.exclusions, PackageExclusion)
    pkg = Package(**data, status=PackageStatus.DRAFT)
    await db[Collections.PACKAGES].insert_one(pkg.to_mongo())
    await _audit(admin, "package.create", pkg.id, None, {"slug": pkg.slug, "title": pkg.title}, request)
    return {"package": _out(pkg.to_mongo())}


@router.patch("/{package_id}")
async def update_package(
    package_id: str, payload: PackagePatch, request: Request,
    admin: dict = Depends(require_admin),
):
    db = get_db()
    existing = await db[Collections.PACKAGES].find_one({"_id": package_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Package not found")

    changes = payload.model_dump(exclude_unset=True)
    if "destination_id" in changes:
        if not await db[Collections.DESTINATIONS].find_one({"_id": changes["destination_id"]}):
            raise HTTPException(status_code=400, detail="destination_id does not exist")

    # Normalise nested collections + money fields.
    if "images" in changes:
        changes["images"] = _ensure_single_cover(_normalise_children(payload.images, PackageImage))
    if "inclusions" in changes:
        changes["inclusions"] = _normalise_children(payload.inclusions, PackageInclusion)
    if "exclusions" in changes:
        changes["exclusions"] = _normalise_children(payload.exclusions, PackageExclusion)
    for k in ("guest_price", "agent_cost", "commission_amount"):
        if k in changes and changes[k] is not None:
            changes[k] = money_to_bson(changes[k])

    if "min_pax" in changes or "max_pax" in changes:
        new_min = changes.get("min_pax", existing.get("min_pax", 1))
        new_max = changes.get("max_pax", existing.get("max_pax", 1))
        if new_max < new_min:
            raise HTTPException(status_code=400, detail="max_pax must be >= min_pax")

    before, after = {}, {}
    updates: dict[str, Any] = {"updated_at": utc_now_iso()}
    for k, v in changes.items():
        current = existing.get(k)
        if isinstance(current, Decimal128):
            current = money_from_bson(current)
            if isinstance(v, Decimal128):
                v_cmp = money_from_bson(v)
            else:
                v_cmp = v
        else:
            v_cmp = v
        if v_cmp != current:
            updates[k] = v
            before[k] = str(current) if isinstance(current, Decimal) else current
            after[k] = str(v_cmp) if isinstance(v_cmp, Decimal) else v_cmp

    if not after:
        return {"ok": True, "changed": False}
    await db[Collections.PACKAGES].update_one({"_id": package_id}, {"$set": updates})
    # Strip embedded arrays from audit "after" for readability.
    for arr in ("images", "inclusions", "exclusions"):
        if arr in after and isinstance(after[arr], list):
            after[arr] = f"{len(after[arr])} item(s)"
        if arr in before and isinstance(before[arr], list):
            before[arr] = f"{len(before[arr])} item(s)"
    await _audit(admin, "package.update", package_id, before, after, request)
    return {"ok": True, "changed": True, "fields": list(after.keys())}


@router.post("/{package_id}/status")
async def set_status(
    package_id: str, payload: StatusIn, request: Request,
    admin: dict = Depends(require_admin),
):
    db = get_db()
    p = await db[Collections.PACKAGES].find_one({"_id": package_id})
    if not p:
        raise HTTPException(status_code=404, detail="Package not found")
    if p.get("status") == payload.status:
        return {"ok": True, "changed": False}
    # If publishing, require a cover image + at least one inclusion for basic hygiene.
    if payload.status == "published":
        imgs = p.get("images", [])
        if not imgs:
            raise HTTPException(status_code=400, detail="Add at least one image before publishing")
        if not p.get("inclusions"):
            raise HTTPException(status_code=400, detail="Add at least one inclusion before publishing")
    await db[Collections.PACKAGES].update_one(
        {"_id": package_id}, {"$set": {"status": payload.status, "updated_at": utc_now_iso()}}
    )
    await _audit(
        admin, f"package.status.{payload.status}", package_id,
        {"status": p.get("status")}, {"status": payload.status}, request,
    )
    return {"ok": True, "changed": True}


@router.delete("/{package_id}")
async def delete_package(package_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Refuse to hard-delete if any booking references this package."""
    db = get_db()
    p = await db[Collections.PACKAGES].find_one({"_id": package_id})
    if not p:
        raise HTTPException(status_code=404, detail="Package not found")
    linked = await db[Collections.BOOKINGS].count_documents({"package_id": package_id})
    if linked > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete — {linked} booking(s) reference this package. Archive it instead.",
        )
    await db[Collections.PACKAGES].delete_one({"_id": package_id})
    await _audit(admin, "package.delete", package_id, {"slug": p["slug"], "title": p["title"]}, None, request)
    return {"ok": True}
