"""Agent customers, bookings and customer quotes under /api/agent."""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field

from core.agent_booking_service import create_agent_booking, parse_future_date, resolve_sellable_package
from core.db import Collections, get_db
from core.payment_service import booking_total_due, derive_status, paid_totals, payments_total, sync_payment_status
from core.quote_pdf import build_quote_pdf
from core.settings_service import get_setting
from models.base import money_from_bson, utc_now_iso
from models.customer import Customer
from models.booking_payment import BookingPayment, PaymentMethod
from routers.agent import _audit, _ledger_row, _m, _q, current_agent

router = APIRouter(prefix="/api/agent", tags=["agent:bookings"])


# --- schemas -------------------------------------------------------------

class CustomerIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=1000)


class CustomerPatch(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=1000)


class BookingIn(BaseModel):
    customer_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    pax: int = Field(ge=1, le=100)
    travel_start_date: str = Field(min_length=10, max_length=10)
    traveler_names: list[str] = Field(default_factory=list, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    paid_on: str = Field(min_length=10, max_length=10)
    reference: Optional[str] = Field(default=None, max_length=120)
    note: Optional[str] = Field(default=None, max_length=400)


class QuoteIn(BaseModel):
    package_id: str = Field(min_length=1)
    pax: int = Field(ge=1, le=100)
    customer_name: Optional[str] = Field(default=None, max_length=120)
    travel_date: Optional[str] = Field(default=None, max_length=10)


# --- helpers -------------------------------------------------------------

def _customer_out(c: dict, bookings_count: Optional[int] = None) -> dict:
    out = {
        "id": c["_id"],
        "first_name": c.get("first_name"), "last_name": c.get("last_name"),
        "full_name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
        "email": c.get("email"), "phone": c.get("phone"),
        "address": c.get("address"), "notes": c.get("notes"),
        "created_at": c.get("created_at"),
    }
    if bookings_count is not None:
        out["bookings_count"] = bookings_count
    return out


def _clean(d: dict) -> dict:
    return {k: (v.strip() or None) if isinstance(v, str) else v for k, v in d.items()}


async def _own_customer(agent_id: str, customer_id: str) -> dict:
    c = await get_db()[Collections.CUSTOMERS].find_one({"_id": customer_id, "agent_id": agent_id})
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


def _booking_out(b: dict, pkg: Optional[dict], cust: Optional[dict], paid: Decimal = Decimal("0.00")) -> dict:
    row = _ledger_row(b, {b.get("package_id"): (pkg or {}).get("title", "Package")})
    unit_retail = _m(b.get("unit_guest_price")) if b.get("total_retail_price") is None else (
        _m(b["total_retail_price"]) / b["pax"]
    )
    return {
        "id": b["_id"],
        "reference_code": b.get("reference_code"),
        "status": b.get("status"),
        "guest_payment_status": b.get("guest_payment_status"),
        "pax": b.get("pax"),
        "package": {"id": pkg["_id"], "title": pkg["title"]} if pkg else None,
        "customer": {"id": cust["_id"], "name": f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip()} if cust else None,
        "travel_start_date": b.get("travel_start_date"),
        "travel_end_date": b.get("travel_end_date"),
        "unit_retail_price": _q(unit_retail),
        "total_retail_price": row["customer_paid"],
        "unit_net_cost": _q(_m(b.get("unit_agent_cost"))),
        "total_net_cost": row["net_cost"],
        "total_markup": row["markup_profit"],
        "total_bonus_commission": row["bonus_commission"],
        "earned": row["earned"],
        "amount_paid": _q(paid),
        "balance_due": _q(max(booking_total_due(b) - paid, Decimal("0.00"))),
        "travelers": [{"full_name": t.get("full_name"), "is_lead": t.get("is_lead", False)} for t in b.get("travelers", [])],
        "status_history": [
            {"to_status": h.get("to_status"), "changed_at": h.get("changed_at"), "note": h.get("note")}
            for h in b.get("status_history", [])
        ],
        "notes": b.get("notes"),
        "created_at": b.get("created_at"),
    }


async def _own_booking(agent_id: str, booking_id: str) -> dict:
    b = await get_db()[Collections.BOOKINGS].find_one({"_id": booking_id, "agent_id": agent_id})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    return b


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


async def _quote_response(ctx: dict, pkg: dict, unit_retail: Decimal, pax: int,
                          customer_name: Optional[str], travel_date: Optional[str], quote_no: str) -> Response:
    db = get_db()
    dest = await db[Collections.DESTINATIONS].find_one({"_id": pkg["destination_id"]})
    brand = await get_setting("brand", {}) or {}
    pdf = build_quote_pdf(
        brand=brand, agent=ctx["profile"], agent_email=ctx["user"].get("email"),
        pkg=pkg, destination=dest, unit_retail=unit_retail, pax=pax,
        customer_name=customer_name, travel_date=travel_date, quote_no=quote_no,
    )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="quote-{quote_no}.pdf"'},
    )


# --- customers -----------------------------------------------------------

@router.get("/customers")
async def list_customers(ctx: dict = Depends(current_agent), q: Optional[str] = Query(default=None, max_length=100)):
    db = get_db()
    agent_id = ctx["profile"]["_id"]
    query: dict = {"agent_id": agent_id}
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"first_name": rx}, {"last_name": rx}, {"email": rx}, {"phone": rx}]
    rows = await db[Collections.CUSTOMERS].find(query).sort([("last_name", 1), ("first_name", 1)]).to_list(length=500)
    counts = {
        r["_id"]: r["n"] async for r in db[Collections.BOOKINGS].aggregate([
            {"$match": {"agent_id": agent_id}}, {"$group": {"_id": "$customer_id", "n": {"$sum": 1}}},
        ])
    }
    return {"customers": [_customer_out(c, counts.get(c["_id"], 0)) for c in rows]}


@router.post("/customers")
async def create_customer(payload: CustomerIn, request: Request, ctx: dict = Depends(current_agent)):
    c = Customer(agent_id=ctx["profile"]["_id"], **_clean(payload.model_dump()))
    doc = c.to_mongo()
    await get_db()[Collections.CUSTOMERS].insert_one(doc)
    await _audit(ctx, "customer.create", "customer", c.id, None, {"name": f"{c.first_name} {c.last_name}"}, request)
    return {"customer": _customer_out(doc, 0)}


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: str, ctx: dict = Depends(current_agent)):
    db = get_db()
    agent_id = ctx["profile"]["_id"]
    c = await _own_customer(agent_id, customer_id)
    bookings = await db[Collections.BOOKINGS].find({"agent_id": agent_id, "customer_id": customer_id}).sort("created_at", -1).to_list(length=200)
    pkgs = {p["_id"]: p async for p in db[Collections.PACKAGES].find({"_id": {"$in": [b["package_id"] for b in bookings]}})}
    paid = await paid_totals([b["_id"] for b in bookings])
    return {
        "customer": _customer_out(c, len(bookings)),
        "bookings": [_booking_out(b, pkgs.get(b["package_id"]), c, paid.get(b["_id"], Decimal("0.00"))) for b in bookings],
    }


@router.patch("/customers/{customer_id}")
async def update_customer(customer_id: str, payload: CustomerPatch, request: Request, ctx: dict = Depends(current_agent)):
    agent_id = ctx["profile"]["_id"]
    c = await _own_customer(agent_id, customer_id)
    changes = _clean(payload.model_dump(exclude_unset=True))
    for k in ("first_name", "last_name"):
        if k in changes and not changes[k]:
            raise HTTPException(status_code=400, detail=f"{k.replace('_', ' ').capitalize()} is required")
    if changes:
        await get_db()[Collections.CUSTOMERS].update_one(
            {"_id": customer_id, "agent_id": agent_id}, {"$set": {**changes, "updated_at": utc_now_iso()}},
        )
        await _audit(ctx, "customer.update", "customer", customer_id, {k: c.get(k) for k in changes}, changes, request)
        c.update(changes)
    return {"customer": _customer_out(c)}


@router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: str, request: Request, ctx: dict = Depends(current_agent)):
    db = get_db()
    agent_id = ctx["profile"]["_id"]
    c = await _own_customer(agent_id, customer_id)
    if await db[Collections.BOOKINGS].count_documents({"customer_id": customer_id}):
        raise HTTPException(status_code=409, detail="This customer has bookings and can't be deleted")
    await db[Collections.CUSTOMERS].delete_one({"_id": customer_id, "agent_id": agent_id})
    await _audit(ctx, "customer.delete", "customer", customer_id, {"name": f"{c['first_name']} {c['last_name']}"}, None, request)
    return {"ok": True}


# --- bookings ------------------------------------------------------------

@router.get("/bookings")
async def list_bookings(
    ctx: dict = Depends(current_agent),
    status: Optional[str] = Query(default=None, pattern="^(pending|confirmed|cancelled|completed)$"),
    payment: Optional[str] = Query(default=None, pattern="^owing$"),
):
    db = get_db()
    q: dict = {"agent_id": ctx["profile"]["_id"]}
    if status:
        q["status"] = status
    if payment == "owing":
        q["status"] = {"$ne": "cancelled"} if not status else status
        q["guest_payment_status"] = {"$ne": "paid"}
    rows = await db[Collections.BOOKINGS].find(q).sort("created_at", -1).to_list(length=500)
    pkgs = {p["_id"]: p async for p in db[Collections.PACKAGES].find({"_id": {"$in": list({b["package_id"] for b in rows})}}, {"title": 1})}
    custs = {c["_id"]: c async for c in db[Collections.CUSTOMERS].find({"_id": {"$in": list({b["customer_id"] for b in rows})}})}
    paid = await paid_totals([b["_id"] for b in rows])
    return {"bookings": [
        _booking_out(b, pkgs.get(b["package_id"]), custs.get(b["customer_id"]), paid.get(b["_id"], Decimal("0.00")))
        for b in rows
    ]}


@router.get("/bookings/{booking_id}")
async def get_booking(booking_id: str, ctx: dict = Depends(current_agent)):
    db = get_db()
    b = await _own_booking(ctx["profile"]["_id"], booking_id)
    pkg = await db[Collections.PACKAGES].find_one({"_id": b["package_id"]})
    cust = await db[Collections.CUSTOMERS].find_one({"_id": b["customer_id"]})
    return {"booking": _booking_out(b, pkg, cust, await payments_total(booking_id))}


@router.post("/bookings")
async def create_booking(payload: BookingIn, request: Request, ctx: dict = Depends(current_agent)):
    b = await create_agent_booking(
        ctx=ctx, customer_id=payload.customer_id, package_id=payload.package_id, pax=payload.pax,
        travel_start_date=payload.travel_start_date, traveler_names=payload.traveler_names,
        notes=payload.notes, ip=_ip(request), ua=request.headers.get("user-agent"),
    )
    db = get_db()
    pkg = await db[Collections.PACKAGES].find_one({"_id": b["package_id"]})
    cust = await db[Collections.CUSTOMERS].find_one({"_id": b["customer_id"]})
    return {"booking": _booking_out(b, pkg, cust)}


# --- customer payments ---------------------------------------------------

def _payment_out(p: dict) -> dict:
    return {
        "id": p["_id"], "amount": _q(_m(p["amount"])), "method": p["method"],
        "paid_on": p["paid_on"], "reference": p.get("reference"), "note": p.get("note"),
        "created_at": p.get("created_at"),
    }


async def _payments_payload(b: dict) -> dict:
    rows = await get_db()[Collections.BOOKING_PAYMENTS].find({"booking_id": b["_id"]}).sort([("paid_on", 1), ("created_at", 1)]).to_list(length=200)
    paid = sum((_m(p["amount"]) for p in rows), Decimal("0.00"))
    due = booking_total_due(b)
    return {
        "payments": [_payment_out(p) for p in rows],
        "total_due": _q(due), "amount_paid": _q(paid),
        "balance_due": _q(max(due - paid, Decimal("0.00"))),
        "guest_payment_status": derive_status(paid, due),
    }


@router.get("/bookings/{booking_id}/payments")
async def list_payments(booking_id: str, ctx: dict = Depends(current_agent)):
    return await _payments_payload(await _own_booking(ctx["profile"]["_id"], booking_id))


@router.post("/bookings/{booking_id}/payments")
async def add_payment(booking_id: str, payload: PaymentIn, request: Request, ctx: dict = Depends(current_agent)):
    b = await _own_booking(ctx["profile"]["_id"], booking_id)
    if b.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="Can't record payments on a cancelled booking")
    try:
        paid_on = date.fromisoformat(payload.paid_on)
    except ValueError:
        raise HTTPException(status_code=400, detail="Payment date must be YYYY-MM-DD")
    if paid_on > datetime.now(timezone.utc).date() + timedelta(days=1):
        raise HTTPException(status_code=400, detail="Payment date can't be in the future")
    remaining = booking_total_due(b) - await payments_total(booking_id)
    amount = payload.amount.quantize(Decimal("0.01"))
    if amount > remaining:
        raise HTTPException(status_code=400, detail=f"Amount is more than the balance due (₱{remaining.quantize(Decimal('0.01')):,})")
    p = BookingPayment(
        booking_id=booking_id, agent_id=ctx["profile"]["_id"], amount=amount, method=payload.method,
        paid_on=paid_on.isoformat(), reference=(payload.reference or "").strip() or None,
        note=(payload.note or "").strip() or None, recorded_by_user_id=ctx["user"]["_id"],
    )
    await get_db()[Collections.BOOKING_PAYMENTS].insert_one(p.to_mongo())
    status = await sync_payment_status(b)
    await _audit(ctx, "booking.payment.add", "booking", booking_id, None,
                 {"payment_id": p.id, "amount": _q(amount), "method": payload.method.value, "guest_payment_status": status}, request)
    return await _payments_payload(b)


@router.delete("/bookings/{booking_id}/payments/{payment_id}")
async def delete_payment(booking_id: str, payment_id: str, request: Request, ctx: dict = Depends(current_agent)):
    b = await _own_booking(ctx["profile"]["_id"], booking_id)
    db = get_db()
    p = await db[Collections.BOOKING_PAYMENTS].find_one({"_id": payment_id, "booking_id": booking_id})
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    await db[Collections.BOOKING_PAYMENTS].delete_one({"_id": payment_id})
    status = await sync_payment_status(b)
    await _audit(ctx, "booking.payment.delete", "booking", booking_id,
                 {"payment_id": payment_id, "amount": _q(_m(p["amount"])), "method": p["method"]},
                 {"guest_payment_status": status}, request)
    return await _payments_payload(b)


# --- quotes --------------------------------------------------------------

@router.post("/quotes/pdf")
async def quote_pdf(payload: QuoteIn, request: Request, ctx: dict = Depends(current_agent)):
    pkg, markup = await resolve_sellable_package(ctx["profile"]["_id"], payload.package_id, payload.pax)
    travel = parse_future_date(payload.travel_date)
    unit_retail = (money_from_bson(pkg["agent_cost"]) + markup).quantize(Decimal("0.01"))
    quote_no = f"Q-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(2).upper()}"
    await _audit(ctx, "quote.generate", "package", pkg["_id"], None,
                 {"quote_no": quote_no, "pax": payload.pax, "unit_retail": str(unit_retail)}, request)
    return await _quote_response(
        ctx, pkg, unit_retail, payload.pax, (payload.customer_name or "").strip() or None,
        travel.strftime("%d %b %Y") if travel else None, quote_no,
    )


@router.get("/bookings/{booking_id}/quote.pdf")
async def booking_quote_pdf(booking_id: str, ctx: dict = Depends(current_agent)):
    db = get_db()
    b = await _own_booking(ctx["profile"]["_id"], booking_id)
    pkg = await db[Collections.PACKAGES].find_one({"_id": b["package_id"]})
    cust = await db[Collections.CUSTOMERS].find_one({"_id": b["customer_id"]})
    out = _booking_out(b, pkg, cust)
    travel = b.get("travel_start_date")
    travel_label = datetime.fromisoformat(travel).strftime("%d %b %Y") if travel else None
    return await _quote_response(
        ctx, pkg, Decimal(out["unit_retail_price"]), b["pax"],
        out["customer"]["name"] if out["customer"] else None, travel_label, b["reference_code"],
    )
