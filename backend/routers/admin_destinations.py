"""Admin CRUD for destinations under /api/admin/destinations."""
from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.db import Collections, get_db
from core.deps import require_role
from models.audit_log import AuditLog
from models.base import utc_now_iso
from models.destination import Destination, DestinationScope

router = APIRouter(prefix="/api/admin/destinations", tags=["admin:destinations"])
require_admin = require_role("admin")


class DestinationIn(BaseModel):
    slug: str = Field(min_length=2, max_length=80, pattern="^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=80)
    scope: DestinationScope
    hero_image_url: Optional[str] = Field(default=None, max_length=800)
    short_description: Optional[str] = Field(default=None, max_length=400)
    long_description: Optional[str] = Field(default=None, max_length=4000)
    featured_on_home: bool = False
    is_active: bool = True


class DestinationPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    country: Optional[str] = Field(default=None, min_length=1, max_length=80)
    scope: Optional[DestinationScope] = None
    hero_image_url: Optional[str] = Field(default=None, max_length=800)
    short_description: Optional[str] = Field(default=None, max_length=400)
    long_description: Optional[str] = Field(default=None, max_length=4000)
    featured_on_home: Optional[bool] = None
    is_active: Optional[bool] = None


def _out(d: dict) -> dict:
    return {**{k: d.get(k) for k in
        ["slug", "name", "country", "scope", "hero_image_url",
         "short_description", "long_description", "featured_on_home",
         "is_active", "created_at", "updated_at"]},
        "id": d["_id"]}


async def _audit(admin, action, target_id, before, after, request):
    await get_db()[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=admin["_id"], actor_role="admin",
            action=action, target_type="destination", target_id=target_id,
            before=before, after=after,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        ).to_mongo()
    )


@router.get("")
async def list_destinations(
    admin: dict = Depends(require_admin),
    scope: Optional[str] = Query(default=None, pattern="^(domestic|international)$"),
    q: Optional[str] = None,
):
    db = get_db()
    qy: dict = {}
    if scope:
        qy["scope"] = scope
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        qy["$or"] = [{"name": rx}, {"country": rx}, {"slug": rx}]

    rows = await db[Collections.DESTINATIONS].find(qy).sort("name", 1).to_list(length=500)

    # attach package counts per destination
    pkg_counts_map: dict[str, dict[str, int]] = {}
    if rows:
        pipeline = [
            {"$match": {"destination_id": {"$in": [r["_id"] for r in rows]}}},
            {"$group": {"_id": {"d": "$destination_id", "s": "$status"}, "n": {"$sum": 1}}},
        ]
        async for agg in db[Collections.PACKAGES].aggregate(pipeline):
            d = agg["_id"]["d"]
            pkg_counts_map.setdefault(d, {})[agg["_id"]["s"]] = agg["n"]

    out = []
    for r in rows:
        base = _out(r)
        base["package_counts"] = pkg_counts_map.get(r["_id"], {})
        out.append(base)
    return {"destinations": out}


@router.post("", status_code=201)
async def create_destination(payload: DestinationIn, request: Request, admin: dict = Depends(require_admin)):
    db = get_db()
    if await db[Collections.DESTINATIONS].find_one({"slug": payload.slug}):
        raise HTTPException(status_code=409, detail="A destination with this slug already exists")
    dest = Destination(**payload.model_dump())
    await db[Collections.DESTINATIONS].insert_one(dest.to_mongo())
    await _audit(admin, "destination.create", dest.id, None, {"slug": dest.slug, "name": dest.name}, request)
    return {"destination": _out(dest.to_mongo())}


@router.get("/{destination_id}")
async def get_destination(destination_id: str, admin: dict = Depends(require_admin)):
    d = await get_db()[Collections.DESTINATIONS].find_one({"_id": destination_id})
    if not d:
        raise HTTPException(status_code=404, detail="Destination not found")
    return {"destination": _out(d)}


@router.patch("/{destination_id}")
async def update_destination(
    destination_id: str, payload: DestinationPatch, request: Request,
    admin: dict = Depends(require_admin),
):
    db = get_db()
    existing = await db[Collections.DESTINATIONS].find_one({"_id": destination_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Destination not found")
    updates: dict[str, Any] = {"updated_at": utc_now_iso()}
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for k, v in payload.model_dump(exclude_unset=True).items():
        if v != existing.get(k):
            updates[k] = v
            before[k] = existing.get(k)
            after[k] = v
    if not after:
        return {"ok": True, "changed": False}
    await db[Collections.DESTINATIONS].update_one({"_id": destination_id}, {"$set": updates})
    await _audit(admin, "destination.update", destination_id, before, after, request)
    return {"ok": True, "changed": True, "fields": list(after.keys())}


@router.delete("/{destination_id}")
async def delete_destination(destination_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Refuses to delete a destination that still has packages.  Use PATCH is_active=false instead."""
    db = get_db()
    d = await db[Collections.DESTINATIONS].find_one({"_id": destination_id})
    if not d:
        raise HTTPException(status_code=404, detail="Destination not found")
    linked = await db[Collections.PACKAGES].count_documents({"destination_id": destination_id})
    if linked > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete — {linked} package(s) reference this destination. Deactivate it instead.",
        )
    await db[Collections.DESTINATIONS].delete_one({"_id": destination_id})
    await _audit(admin, "destination.delete", destination_id, {"slug": d["slug"], "name": d["name"]}, None, request)
    return {"ok": True}
