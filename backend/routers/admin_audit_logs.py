"""Global audit-log timeline for admins (read-only)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.db import Collections, get_db
from core.deps import require_role

router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin:audit-logs"])

require_admin = require_role("admin")


def _row_out(r: dict, actor: Optional[dict]) -> dict:
    return {
        "id": str(r.get("_id")),
        "created_at": r.get("created_at"),
        "actor_user_id": r.get("actor_user_id"),
        "actor_role": r.get("actor_role"),
        "actor": (
            {"id": actor["_id"], "email": actor.get("email"),
             "display_name": actor.get("display_name")}
            if actor else None
        ),
        "action": r.get("action"),
        "target_type": r.get("target_type"),
        "target_id": r.get("target_id"),
        "before": r.get("before"),
        "after": r.get("after"),
        "ip": r.get("ip"),
        "user_agent": r.get("user_agent"),
        "note": r.get("note"),
    }


@router.get("")
async def list_audit_logs(
    admin: dict = Depends(require_admin),
    actor_user_id: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None, description="exact or prefix (e.g. 'fund_request.')"),
    target_type: Optional[str] = Query(default=None),
    target_id: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    db = get_db()
    q: dict = {}
    if actor_user_id:
        q["actor_user_id"] = actor_user_id
    if action:
        if action.endswith("."):  # prefix search
            import re as _re
            q["action"] = {"$regex": f"^{_re.escape(action)}"}
        else:
            q["action"] = action
    if target_type:
        q["target_type"] = target_type
    if target_id:
        q["target_id"] = target_id
    if date_from or date_to:
        rng: dict = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        q["created_at"] = rng

    total = await db[Collections.AUDIT_LOGS].count_documents(q)
    rows = await (
        db[Collections.AUDIT_LOGS].find(q).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )
    actor_ids = list({r["actor_user_id"] for r in rows if r.get("actor_user_id")})
    actors = {
        u["_id"]: u
        async for u in db[Collections.USERS].find(
            {"_id": {"$in": actor_ids}},
            {"email": 1, "display_name": 1},
        )
    }
    return {
        "audit_logs": [_row_out(r, actors.get(r.get("actor_user_id"))) for r in rows],
        "page": page, "page_size": page_size, "total": total,
    }


@router.get("/actions")
async def list_actions(admin: dict = Depends(require_admin)):
    """Distinct action verbs (for a filter dropdown)."""
    db = get_db()
    actions = await db[Collections.AUDIT_LOGS].distinct("action")
    target_types = await db[Collections.AUDIT_LOGS].distinct("target_type")
    return {"actions": sorted(a for a in actions if a),
            "target_types": sorted(t for t in target_types if t)}
