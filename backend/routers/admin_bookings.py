"""Admin bookings management under /api/admin/bookings."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core import booking_service
from core.db import Collections, get_db
from core.payment_service import booking_total_due
from core.deps import require_role
from models.base import money_from_bson

router = APIRouter(prefix="/api/admin/bookings", tags=["admin:bookings"])
require_admin = require_role("admin")


# --- schemas -------------------------------------------------------------

class ChangeStatusIn(BaseModel):
    status: str = Field(pattern="^(pending|confirmed|cancelled|completed)$")
    refund: bool = False
    reason: Optional[str] = Field(default=None, max_length=400)


class GuestPaymentStatusIn(BaseModel):
    status: str = Field(pattern="^(unpaid|partial|paid)$")
    note: Optional[str] = Field(default=None, max_length=400)


# --- serialisers ---------------------------------------------------------

def _booking_summary(b: dict, agent: Optional[dict], package: Optional[dict], customer: Optional[dict]) -> dict:
    return {
        "id": b["_id"],
        "reference_code": b["reference_code"],
        "status": b["status"],
        "guest_payment_status": b.get("guest_payment_status"),
        "pax": b["pax"],
        "total_agent_cost": str(money_from_bson(b["total_agent_cost"])),
        "total_guest_price": str(money_from_bson(b["total_guest_price"])),
        "total_commission_amount": str(money_from_bson(b["total_commission_amount"])),
        "currency": b.get("currency", "PHP"),
        "travel_start_date": b.get("travel_start_date"),
        "travel_end_date": b.get("travel_end_date"),
        "created_at": b["created_at"],
        "agent": {
            "id": agent["_id"], "display_name": agent["display_name"], "email_hint": None,
        } if agent else None,
        "package": {
            "id": package["_id"], "slug": package["slug"], "title": package["title"],
        } if package else None,
        "customer": {
            "id": customer["_id"],
            "name": f"{customer.get('first_name','')} {customer.get('last_name','')}".strip(),
        } if customer else None,
    }


def _booking_detail(b: dict, agent: dict, agent_user: dict, package: dict, customer: dict) -> dict:
    summary = _booking_summary(b, agent, package, customer)
    if summary["agent"]:
        summary["agent"]["email"] = agent_user.get("email") if agent_user else None
    return {
        **summary,
        "unit_agent_cost": str(money_from_bson(b["unit_agent_cost"])),
        "unit_guest_price": str(money_from_bson(b["unit_guest_price"])),
        "unit_commission_amount": str(money_from_bson(b["unit_commission_amount"])),
        "total_markup_amount": (
            str(money_from_bson(b["total_markup_amount"])) if b.get("total_markup_amount") is not None else None
        ),
        "travelers": b.get("travelers", []),
        "status_history": b.get("status_history", []),
        "notes": b.get("notes"),
    }


# --- endpoints -----------------------------------------------------------

@router.get("")
async def list_bookings(
    admin: dict = Depends(require_admin),
    status: Optional[str] = Query(default=None, pattern="^(pending|confirmed|cancelled|completed)$"),
    agent_id: Optional[str] = None,
    package_slug: Optional[str] = None,
    q: Optional[str] = Query(default=None, description="reference_code search"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    db = get_db()
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if agent_id:
        query["agent_id"] = agent_id
    if q:
        query["reference_code"] = {"$regex": re.escape(q.strip()), "$options": "i"}
    if package_slug:
        pkg = await db[Collections.PACKAGES].find_one({"slug": package_slug}, {"_id": 1})
        if pkg:
            query["package_id"] = pkg["_id"]
        else:
            return {"bookings": [], "page": page, "page_size": page_size, "total": 0}

    total = await db[Collections.BOOKINGS].count_documents(query)
    rows = await (
        db[Collections.BOOKINGS].find(query).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )

    # Batch-load agents, packages, customers referenced by this page.
    agent_ids = {r["agent_id"] for r in rows}
    package_ids = {r["package_id"] for r in rows}
    customer_ids = {r["customer_id"] for r in rows}
    agents = {a["_id"]: a async for a in db[Collections.AGENT_PROFILES].find({"_id": {"$in": list(agent_ids)}})}
    packages = {p["_id"]: p async for p in db[Collections.PACKAGES].find({"_id": {"$in": list(package_ids)}})}
    customers = {c["_id"]: c async for c in db[Collections.CUSTOMERS].find({"_id": {"$in": list(customer_ids)}})}

    return {
        "bookings": [
            _booking_summary(
                r,
                agents.get(r["agent_id"]),
                packages.get(r["package_id"]),
                customers.get(r["customer_id"]),
            ) for r in rows
        ],
        "page": page, "page_size": page_size, "total": total,
    }


@router.get("/{booking_id}")
async def get_booking(booking_id: str, admin: dict = Depends(require_admin)):
    db = get_db()
    b = await db[Collections.BOOKINGS].find_one({"_id": booking_id})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    agent = await db[Collections.AGENT_PROFILES].find_one({"_id": b["agent_id"]}) or {}
    agent_user = await db[Collections.USERS].find_one({"_id": agent.get("user_id")}) if agent else None
    package = await db[Collections.PACKAGES].find_one({"_id": b["package_id"]}) or {}
    customer = await db[Collections.CUSTOMERS].find_one({"_id": b["customer_id"]}) or {}
    payments = await db[Collections.BOOKING_PAYMENTS].find({"booking_id": booking_id}).sort("paid_on", 1).to_list(length=200)
    paid = sum((money_from_bson(p["amount"]) for p in payments), Decimal("0.00"))
    detail = _booking_detail(b, agent, agent_user, package, customer)
    detail["payments"] = [
        {"id": p["_id"], "amount": str(money_from_bson(p["amount"])), "method": p["method"],
         "paid_on": p["paid_on"], "reference": p.get("reference")}
        for p in payments
    ]
    detail["amount_paid"] = str(paid)
    detail["balance_due"] = str(max(booking_total_due(b) - paid, Decimal("0.00")))

    return {"booking": detail}


@router.patch("/{booking_id}/status")
async def change_booking_status(
    booking_id: str, payload: ChangeStatusIn, request: Request,
    admin: dict = Depends(require_admin),
):
    result = await booking_service.change_status(
        booking_id=booking_id,
        new_status=payload.status,
        refund=payload.refund,
        reason=payload.reason,
        admin=admin,
        admin_ip=(request.client.host if request.client else None),
        admin_ua=request.headers.get("user-agent"),
    )
    return {"ok": True, **result}


@router.patch("/{booking_id}/guest-payment-status")
async def set_guest_payment_status(
    booking_id: str, payload: GuestPaymentStatusIn, request: Request,
    admin: dict = Depends(require_admin),
):
    raise HTTPException(
        status_code=409,
        detail="Customer payment status now follows the payments the agent records",
    )


@router.get("/{booking_id}/transactions")
async def list_booking_transactions(booking_id: str, admin: dict = Depends(require_admin)):
    db = get_db()
    b = await db[Collections.BOOKINGS].find_one({"_id": booking_id})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    rows = await (
        db[Collections.TRANSACTIONS].find({"ref_type": "booking", "ref_id": booking_id})
        .sort("created_at", 1).to_list(length=200)
    )
    txns = []
    for r in rows:
        r["id"] = r.pop("_id")
        r["amount"] = str(money_from_bson(r["amount"]))
        r["balance_after"] = str(money_from_bson(r["balance_after"]))
        txns.append(r)
    return {"transactions": txns}
