"""Agent portal endpoints under /api/agent.

Isolation: the agent profile is always resolved from the JWT; no endpoint
accepts an agent id from the client.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.db import Collections, get_db
from core.deps import require_role
from core.payment_service import booking_total_due, paid_totals
from core.settings_service import get_markup_bounds, get_topup_bounds
from models.audit_log import AuditLog
from models.base import money_from_bson, money_to_bson, utc_now_iso
from models.fund_request import FundRequest, FundRequestStatus
from models.markup import AgentPackageMarkup

router = APIRouter(prefix="/api/agent", tags=["agent"])

MAX_PENDING_FUND_REQUESTS = 5
ZERO = Decimal("0.00")


async def current_agent(user: dict = Depends(require_role("agent"))) -> dict:
    profile = await get_db()[Collections.AGENT_PROFILES].find_one({"user_id": user["_id"]})
    if not profile:
        raise HTTPException(status_code=500, detail="Agent profile missing for user")
    if profile.get("status") == "disabled":
        raise HTTPException(status_code=403, detail="Agent account is disabled")
    return {"user": user, "profile": profile}


# --- schemas -------------------------------------------------------------

class MarkupIn(BaseModel):
    markup_amount: Decimal = Field(ge=0)


class FundRequestIn(BaseModel):
    amount: Decimal = Field(gt=0)
    reference_no: Optional[str] = Field(default=None, max_length=120)
    note: Optional[str] = Field(default=None, max_length=400)


class ProfileIn(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=300)


# --- helpers -------------------------------------------------------------

def _m(v) -> Decimal:
    return money_from_bson(v) or ZERO


def _q(v: Decimal) -> str:
    return str(v.quantize(Decimal("0.01")))


async def _audit(ctx: dict, action: str, target_type: str, target_id: str, before, after, request: Request):
    await get_db()[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=ctx["user"]["_id"], actor_role="agent",
            action=action, target_type=target_type, target_id=target_id,
            before=before, after=after,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        ).to_mongo()
    )


def _markup_state(markup: Optional[Decimal], bounds: tuple[Decimal, Decimal]) -> str:
    if markup is None:
        return "unset"
    lo, hi = bounds
    return "ok" if lo <= markup <= hi else "out_of_range"


def _package_out(p: dict, dest: Optional[dict], markup: Optional[Decimal], bounds) -> dict:
    cover = next((i for i in p.get("images", []) if i.get("is_cover")), None) or (
        p.get("images") or [None]
    )[0]
    net = _m(p["agent_cost"])
    state = _markup_state(markup, bounds)
    return {
        "id": p["_id"],
        "slug": p["slug"],
        "title": p["title"],
        "summary": p.get("summary"),
        "duration_days": p.get("duration_days"),
        "duration_nights": p.get("duration_nights"),
        "min_pax": p.get("min_pax"),
        "max_pax": p.get("max_pax"),
        "cover_image_url": cover.get("url") if cover else None,
        "destination": {"id": dest["_id"], "name": dest["name"], "country": dest.get("country")} if dest else None,
        "net_cost": _q(net),
        "public_price": _q(_m(p.get("guest_price"))),
        "bonus_commission": _q(_m(p.get("commission_amount"))),
        "markup_amount": _q(markup) if markup is not None else None,
        "retail_price": _q(net + markup) if markup is not None else None,
        "markup_status": state,
        "bookable": state == "ok",
        "inclusions": [i.get("text") for i in sorted(p.get("inclusions", []), key=lambda x: x.get("sort_order", 0))],
        "exclusions": [i.get("text") for i in sorted(p.get("exclusions", []), key=lambda x: x.get("sort_order", 0))],
        "highlights": p.get("highlights"),
        "itinerary": p.get("itinerary"),
    }


def _ledger_row(b: dict, pkg_titles: dict) -> dict:
    net = _m(b.get("total_agent_cost"))
    if b.get("total_retail_price") is not None:
        retail = _m(b["total_retail_price"])
        markup = _m(b.get("total_markup_amount"))
    else:
        retail = _m(b.get("total_guest_price"))
        markup = max(retail - net, ZERO)
    commission = _m(b.get("total_commission_amount"))
    cancelled = b.get("status") == "cancelled"
    earned = ZERO if cancelled else markup + commission
    return {
        "id": b["_id"],
        "date": b.get("created_at"),
        "booking_ref": b.get("reference_code"),
        "description": f"{pkg_titles.get(b.get('package_id'), 'Package')} · {b.get('pax', 0)} pax",
        "net_cost": _q(net),
        "customer_paid": _q(retail),
        "markup_profit": _q(ZERO if cancelled else markup),
        "bonus_commission": _q(ZERO if cancelled else commission),
        "earned": _q(earned),
        "status": b.get("status"),
    }


async def _markups_for(agent_id: str) -> dict:
    return {
        m["package_id"]: _m(m["markup_amount"])
        async for m in get_db()[Collections.AGENT_PACKAGE_MARKUPS].find({"agent_id": agent_id})
    }


async def _ledger_rows(agent_id: str, limit: Optional[int] = None) -> list[dict]:
    db = get_db()
    cursor = db[Collections.BOOKINGS].find({"agent_id": agent_id}).sort("created_at", -1)
    if limit:
        cursor = cursor.limit(limit)
    bookings = await cursor.to_list(length=None)
    pkg_ids = list({b.get("package_id") for b in bookings})
    titles = {
        p["_id"]: p["title"]
        async for p in db[Collections.PACKAGES].find({"_id": {"$in": pkg_ids}}, {"title": 1})
    }
    return [_ledger_row(b, titles) for b in bookings]


def _fr_out(fr: dict) -> dict:
    return {
        "id": fr["_id"],
        "amount": _q(_m(fr["amount"])),
        "reference_no": fr.get("reference_no"),
        "note": fr.get("note"),
        "status": fr.get("status"),
        "decision_note": fr.get("decision_note"),
        "decided_at": fr.get("decided_at"),
        "created_at": fr.get("created_at"),
    }


# --- dashboard -----------------------------------------------------------

@router.get("/dashboard")
async def dashboard(ctx: dict = Depends(current_agent)):
    db = get_db()
    profile = ctx["profile"]
    agent_id = profile["_id"]
    rows = await _ledger_rows(agent_id)
    bounds = await get_markup_bounds()
    markups = await _markups_for(agent_id)
    published = await db[Collections.PACKAGES].find({"status": "published"}, {"_id": 1}).to_list(length=None)
    needs_attention = sum(
        1 for p in published if _markup_state(markups.get(p["_id"]), bounds) != "ok"
    )
    status_counts: dict[str, int] = {}
    for r in rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    live = await db[Collections.BOOKINGS].find(
        {"agent_id": agent_id, "status": {"$ne": "cancelled"}, "guest_payment_status": {"$ne": "paid"}},
    ).to_list(length=None)
    paid = await paid_totals([b["_id"] for b in live])
    outstanding = sum((max(booking_total_due(b) - paid.get(b["_id"], ZERO), ZERO) for b in live), ZERO)
    return {
        "agent": {
            "display_name": profile.get("display_name"),
            "agency_name": profile.get("agency_name"),
        },
        "booking_balance": _q(_m(profile["booking_account"]["balance"])),
        "total_earned": _q(sum((Decimal(r["earned"]) for r in rows), ZERO)),
        "total_markup_profit": _q(sum((Decimal(r["markup_profit"]) for r in rows), ZERO)),
        "total_bonus_commission": _q(sum((Decimal(r["bonus_commission"]) for r in rows), ZERO)),
        "bookings_total": len(rows),
        "bookings_by_status": status_counts,
        "customer_balance_due": _q(outstanding),
        "bookings_owing": sum(1 for b in live if booking_total_due(b) - paid.get(b["_id"], ZERO) > 0),
        "pending_fund_requests": await db[Collections.FUND_REQUESTS].count_documents(
            {"agent_id": agent_id, "status": "pending"}
        ),
        "packages_published": len(published),
        "packages_needing_markup": needs_attention,
        "markup_bounds": {"min": _q(bounds[0]), "max": _q(bounds[1])},
        "recent_ledger": rows[:5],
    }


# --- catalog + markups ---------------------------------------------------

@router.get("/packages")
async def list_packages(
    ctx: dict = Depends(current_agent),
    q: Optional[str] = Query(default=None, max_length=100),
):
    db = get_db()
    query: dict = {"status": "published"}
    if q:
        query["title"] = {"$regex": re.escape(q), "$options": "i"}
    pkgs = await db[Collections.PACKAGES].find(query).sort("title", 1).to_list(length=None)
    dest_ids = list({p["destination_id"] for p in pkgs})
    dests = {d["_id"]: d async for d in db[Collections.DESTINATIONS].find({"_id": {"$in": dest_ids}})}
    bounds = await get_markup_bounds()
    markups = await _markups_for(ctx["profile"]["_id"])
    return {
        "packages": [_package_out(p, dests.get(p["destination_id"]), markups.get(p["_id"]), bounds) for p in pkgs],
        "markup_bounds": {"min": _q(bounds[0]), "max": _q(bounds[1])},
    }


async def _published_package(package_id: str) -> dict:
    pkg = await get_db()[Collections.PACKAGES].find_one({"_id": package_id, "status": "published"})
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


@router.get("/packages/{package_id}")
async def get_package(package_id: str, ctx: dict = Depends(current_agent)):
    db = get_db()
    pkg = await _published_package(package_id)
    dest = await db[Collections.DESTINATIONS].find_one({"_id": pkg["destination_id"]})
    m = await db[Collections.AGENT_PACKAGE_MARKUPS].find_one(
        {"agent_id": ctx["profile"]["_id"], "package_id": package_id}
    )
    bounds = await get_markup_bounds()
    return {
        "package": _package_out(pkg, dest, _m(m["markup_amount"]) if m else None, bounds),
        "markup_bounds": {"min": _q(bounds[0]), "max": _q(bounds[1])},
    }


@router.put("/packages/{package_id}/markup")
async def set_markup(
    package_id: str, payload: MarkupIn, request: Request,
    ctx: dict = Depends(current_agent),
):
    pkg = await _published_package(package_id)
    lo, hi = await get_markup_bounds()
    amount = payload.markup_amount.quantize(Decimal("0.01"))
    if amount < lo or amount > hi:
        raise HTTPException(status_code=400, detail=f"Markup must be between ₱{lo} and ₱{hi} per pax")

    db = get_db()
    agent_id = ctx["profile"]["_id"]
    existing = await db[Collections.AGENT_PACKAGE_MARKUPS].find_one(
        {"agent_id": agent_id, "package_id": package_id}
    )
    before = _q(_m(existing["markup_amount"])) if existing else None
    if existing:
        await db[Collections.AGENT_PACKAGE_MARKUPS].update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "markup_amount": money_to_bson(amount),
                "updated_by_user_id": ctx["user"]["_id"],
                "updated_at": utc_now_iso(),
            }},
        )
        markup_id = existing["_id"]
    else:
        doc = AgentPackageMarkup(
            agent_id=agent_id, package_id=package_id,
            markup_amount=amount, updated_by_user_id=ctx["user"]["_id"],
        )
        await db[Collections.AGENT_PACKAGE_MARKUPS].insert_one(doc.to_mongo())
        markup_id = doc.id
    await _audit(
        ctx, "agent.markup.set", "agent_package_markup", markup_id,
        {"package_id": package_id, "markup_amount": before},
        {"package_id": package_id, "markup_amount": _q(amount)},
        request,
    )
    dest = await db[Collections.DESTINATIONS].find_one({"_id": pkg["destination_id"]})
    return {"package": _package_out(pkg, dest, amount, (lo, hi))}


# --- fund requests -------------------------------------------------------

@router.get("/fund-requests")
async def list_fund_requests(
    ctx: dict = Depends(current_agent),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    db = get_db()
    q = {"agent_id": ctx["profile"]["_id"]}
    total = await db[Collections.FUND_REQUESTS].count_documents(q)
    rows = await (
        db[Collections.FUND_REQUESTS].find(q).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )
    lo, hi = await get_topup_bounds()
    return {
        "fund_requests": [_fr_out(r) for r in rows],
        "page": page, "page_size": page_size, "total": total,
        "topup_bounds": {"min": _q(lo), "max": _q(hi)},
    }


@router.post("/fund-requests")
async def create_fund_request(
    payload: FundRequestIn, request: Request, ctx: dict = Depends(current_agent),
):
    lo, hi = await get_topup_bounds()
    if payload.amount < lo or payload.amount > hi:
        raise HTTPException(status_code=400, detail=f"Amount must be between ₱{lo} and ₱{hi}")
    db = get_db()
    agent_id = ctx["profile"]["_id"]
    pending = await db[Collections.FUND_REQUESTS].count_documents({"agent_id": agent_id, "status": "pending"})
    if pending >= MAX_PENDING_FUND_REQUESTS:
        raise HTTPException(
            status_code=409,
            detail=f"You already have {pending} pending requests. Wait for a decision before filing more.",
        )
    fr = FundRequest(
        agent_id=agent_id,
        amount=payload.amount,
        reference_no=(payload.reference_no or "").strip() or None,
        note=(payload.note or "").strip() or None,
        status=FundRequestStatus.PENDING,
    )
    await db[Collections.FUND_REQUESTS].insert_one(fr.to_mongo())
    await _audit(
        ctx, "fund_request.create", "fund_request", fr.id, None,
        {"amount": _q(payload.amount), "reference_no": fr.reference_no}, request,
    )
    return {"fund_request": _fr_out(fr.to_mongo())}


# --- ledger + wallet -----------------------------------------------------

@router.get("/ledger")
async def ledger(ctx: dict = Depends(current_agent)):
    rows = await _ledger_rows(ctx["profile"]["_id"])
    live = [r for r in rows if r["status"] != "cancelled"]
    return {
        "rows": rows,
        "totals": {
            "net_cost": _q(sum((Decimal(r["net_cost"]) for r in live), ZERO)),
            "customer_paid": _q(sum((Decimal(r["customer_paid"]) for r in live), ZERO)),
            "earned": _q(sum((Decimal(r["earned"]) for r in live), ZERO)),
        },
    }


@router.get("/transactions")
async def wallet_transactions(
    ctx: dict = Depends(current_agent),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    db = get_db()
    q = {"agent_id": ctx["profile"]["_id"], "account_kind": "booking"}
    total = await db[Collections.TRANSACTIONS].count_documents(q)
    rows = await (
        db[Collections.TRANSACTIONS].find(q).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )
    return {
        "transactions": [
            {
                "id": t["_id"], "type": t.get("type"),
                "amount": _q(_m(t["amount"])),
                "balance_after": _q(_m(t["balance_after"])),
                "note": t.get("note"), "ref_type": t.get("ref_type"),
                "created_at": t.get("created_at"),
            }
            for t in rows
        ],
        "page": page, "page_size": page_size, "total": total,
    }


# --- notifications -------------------------------------------------------

@router.get("/notifications")
async def list_notifications(ctx: dict = Depends(current_agent), limit: int = Query(default=20, ge=1, le=100)):
    db = get_db()
    uid = ctx["user"]["_id"]
    rows = await db[Collections.NOTIFICATIONS].find({"user_id": uid}).sort("created_at", -1).limit(limit).to_list(length=limit)
    return {
        "notifications": [
            {
                "id": n["_id"], "kind": n.get("kind"), "title": n.get("title"), "body": n.get("body"),
                "ref_type": n.get("ref_type"), "ref_id": n.get("ref_id"),
                "is_read": bool(n.get("is_read")), "created_at": n.get("created_at"),
            }
            for n in rows
        ],
        "unread_count": await db[Collections.NOTIFICATIONS].count_documents({"user_id": uid, "is_read": False}),
    }


@router.post("/notifications/read-all")
async def read_all_notifications(ctx: dict = Depends(current_agent)):
    now = utc_now_iso()
    res = await get_db()[Collections.NOTIFICATIONS].update_many(
        {"user_id": ctx["user"]["_id"], "is_read": False},
        {"$set": {"is_read": True, "read_at": now, "updated_at": now}},
    )
    return {"ok": True, "updated": res.modified_count}


@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: str, ctx: dict = Depends(current_agent)):
    now = utc_now_iso()
    res = await get_db()[Collections.NOTIFICATIONS].update_one(
        {"_id": notification_id, "user_id": ctx["user"]["_id"]},
        {"$set": {"is_read": True, "read_at": now, "updated_at": now}},
    )
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


# --- profile -------------------------------------------------------------

def _profile_out(ctx: dict) -> dict:
    p, u = ctx["profile"], ctx["user"]
    return {
        "email": u.get("email"),
        "display_name": p.get("display_name"),
        "agency_name": p.get("agency_name"),
        "phone": p.get("phone"),
        "address": p.get("address"),
        "status": p.get("status"),
        "member_since": p.get("created_at"),
    }


@router.get("/profile")
async def get_profile(ctx: dict = Depends(current_agent)):
    return {"profile": _profile_out(ctx)}


@router.patch("/profile")
async def update_profile(payload: ProfileIn, request: Request, ctx: dict = Depends(current_agent)):
    changes = {
        k: (v.strip() or None) if isinstance(v, str) else v
        for k, v in payload.model_dump(exclude_unset=True).items()
    }
    if not changes:
        return {"profile": _profile_out(ctx)}
    before = {k: ctx["profile"].get(k) for k in changes}
    await get_db()[Collections.AGENT_PROFILES].update_one(
        {"_id": ctx["profile"]["_id"]},
        {"$set": {**changes, "updated_at": utc_now_iso()}},
    )
    await _audit(ctx, "agent.profile.update", "agent", ctx["profile"]["_id"], before, changes, request)
    ctx["profile"].update(changes)
    return {"profile": _profile_out(ctx)}
