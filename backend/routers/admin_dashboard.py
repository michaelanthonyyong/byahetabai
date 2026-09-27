"""Admin dashboard aggregations + audit log feed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.db import Collections, get_db
from core.deps import require_role
from core.financial_service import sum_agent_balances

router = APIRouter(prefix="/api/admin", tags=["admin:dashboard"])
require_admin = require_role("admin")


@router.get("/dashboard")
async def dashboard(admin: dict = Depends(require_admin)):
    db = get_db()

    # Agent counts by status.
    agent_status_counts = {"active": 0, "invited": 0, "disabled": 0}
    async for row in db[Collections.AGENT_PROFILES].aggregate([
        {"$group": {"_id": "$status", "n": {"$sum": 1}}}
    ]):
        agent_status_counts[row["_id"]] = row["n"]

    # Package + destination counts.
    packages_published = await db[Collections.PACKAGES].count_documents({"status": "published"})
    packages_draft = await db[Collections.PACKAGES].count_documents({"status": "draft"})
    destinations_active = await db[Collections.DESTINATIONS].count_documents({"is_active": True})

    # Pending workflow counts (all zero at this phase — informational).
    pending_fund_requests = await db[Collections.FUND_REQUESTS].count_documents({"status": "pending"})
    pending_withdrawals = await db[Collections.COMMISSION_WITHDRAWALS].count_documents({"status": "pending"})
    total_bookings = await db[Collections.BOOKINGS].count_documents({})
    new_contact_messages = await db["contact_messages"].count_documents({"status": "new"})

    balances = await sum_agent_balances()

    # Last 10 audit-log entries.
    audit_rows = await (
        db[Collections.AUDIT_LOGS]
        .find({}, {"_id": 1, "actor_user_id": 1, "actor_role": 1, "action": 1,
                   "target_type": 1, "target_id": 1, "created_at": 1, "after": 1, "note": 1})
        .sort("created_at", -1).limit(10).to_list(length=10)
    )
    audit = []
    for r in audit_rows:
        r["id"] = r.pop("_id")
        audit.append(r)

    return {
        "agent_counts": {
            "active": agent_status_counts["active"],
            "invited": agent_status_counts["invited"],
            "disabled": agent_status_counts["disabled"],
            "total": sum(agent_status_counts.values()),
        },
        "catalog": {
            "packages_published": packages_published,
            "packages_draft": packages_draft,
            "destinations_active": destinations_active,
        },
        "workflow": {
            "pending_fund_requests": pending_fund_requests,
            "pending_withdrawals": pending_withdrawals,
            "total_bookings": total_bookings,
            "new_contact_messages": new_contact_messages,
        },
        "balances": balances,
        "recent_audit": audit,
        "currency": "PHP",
    }


# Note: the global audit-log feed (with actor lookup + entity/date filters)
# lives in routers/admin_audit_logs.py. This module is dashboard-only.
