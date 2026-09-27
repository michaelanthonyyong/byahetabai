"""Admin inbox for the public contact form.

Statuses: new → read → responded → archived.  Admin can also add an
internal note that never leaves the portal.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.db import Collections, get_db
from core.deps import require_role
from models.audit_log import AuditLog
from models.base import utc_now_iso

router = APIRouter(prefix="/api/admin/contacts", tags=["admin:contacts"])

require_admin = require_role("admin")

VALID_STATUSES = ("new", "read", "responded", "archived")


class UpdateContactIn(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(new|read|responded|archived)$")
    internal_note: Optional[str] = Field(default=None, max_length=2000)


def _row_out(r: dict) -> dict:
    return {
        "id": str(r.get("_id")),
        "name": r.get("name"),
        "email": r.get("email"),
        "phone": r.get("phone"),
        "subject": r.get("subject"),
        "message": r.get("message"),
        "package_slug": r.get("package_slug"),
        "status": r.get("status", "new"),
        "internal_note": r.get("internal_note"),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }


async def _write_audit(admin: dict, action: str, target_id: str, before, after, request: Request):
    await get_db()[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=admin["_id"], actor_role="admin",
            action=action, target_type="contact_message", target_id=target_id,
            before=before, after=after,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        ).to_mongo()
    )


@router.get("")
async def list_contacts(
    admin: dict = Depends(require_admin),
    status: Optional[str] = Query(default=None, pattern="^(new|read|responded|archived)$"),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    db = get_db()
    query: dict = {}
    if status:
        query["status"] = status
    if q:
        import re as _re
        rx = {"$regex": _re.escape(q.strip()), "$options": "i"}
        query["$or"] = [
            {"name": rx}, {"email": rx}, {"subject": rx}, {"message": rx},
        ]
    total = await db[Collections.CONTACT_MESSAGES].count_documents(query)
    rows = await (
        db[Collections.CONTACT_MESSAGES].find(query).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )
    new_count = await db[Collections.CONTACT_MESSAGES].count_documents({"status": "new"})
    return {
        "contacts": [_row_out(r) for r in rows],
        "page": page, "page_size": page_size, "total": total,
        "new_count": new_count,
    }


@router.get("/{contact_id}")
async def get_contact(contact_id: str, admin: dict = Depends(require_admin)):
    db = get_db()
    row = await _find_one(contact_id)
    if not row:
        raise HTTPException(status_code=404, detail="Contact message not found")
    # Auto-mark 'new' as 'read' the first time an admin opens it.
    if row.get("status") == "new":
        await db[Collections.CONTACT_MESSAGES].update_one(
            {"_id": row["_id"]},
            {"$set": {"status": "read", "updated_at": utc_now_iso()}},
        )
        row["status"] = "read"
    return {"contact": _row_out(row)}


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: str, payload: UpdateContactIn, request: Request,
    admin: dict = Depends(require_admin),
):
    db = get_db()
    row = await _find_one(contact_id)
    if not row:
        raise HTTPException(status_code=404, detail="Contact message not found")

    updates: dict = {"updated_at": utc_now_iso()}
    before: dict = {}
    after: dict = {}
    if payload.status and payload.status != row.get("status"):
        before["status"] = row.get("status")
        after["status"] = payload.status
        updates["status"] = payload.status
    if payload.internal_note is not None and payload.internal_note != (row.get("internal_note") or ""):
        before["internal_note"] = row.get("internal_note")
        after["internal_note"] = payload.internal_note
        updates["internal_note"] = payload.internal_note

    if not after:
        return {"ok": True, "changed": False}

    await db[Collections.CONTACT_MESSAGES].update_one({"_id": row["_id"]}, {"$set": updates})
    await _write_audit(admin, "contact.update", str(row["_id"]), before, after, request)
    return {"ok": True, "changed": True, "fields": list(after.keys())}


async def _find_one(contact_id: str) -> Optional[dict]:
    """Contact IDs from Mongo are ObjectIds. Support both str-repr and native."""
    db = get_db()
    row = await db[Collections.CONTACT_MESSAGES].find_one({"_id": contact_id})
    if row:
        return row
    try:
        from bson import ObjectId
        return await db[Collections.CONTACT_MESSAGES].find_one({"_id": ObjectId(contact_id)})
    except Exception:
        return None
