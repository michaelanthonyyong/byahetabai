"""Private, expiring share links for customer quotes and receipts.

Agent side: /api/agent/share-links (create, list, revoke).
Public side: /api/share/{token} streams the PDF inline (no login).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from core.agent_booking_service import parse_future_date, resolve_sellable_package
from core.db import Collections, get_db
from models.base import money_from_bson, utc_now_iso
from routers.agent import _audit, current_agent
from routers.agent_bookings import (
    _own_booking, pdf_response, receipt_number, render_booking_quote, render_quote, render_receipt,
)

router = APIRouter(tags=["share"])

LINK_DAYS = 30


class ShareIn(BaseModel):
    kind: Literal["quote", "booking_quote", "receipt"]
    booking_id: Optional[str] = None
    payment_id: Optional[str] = None
    package_id: Optional[str] = None
    pax: Optional[int] = Field(default=None, ge=1, le=100)
    customer_name: Optional[str] = Field(default=None, max_length=120)
    travel_date: Optional[str] = Field(default=None, max_length=10)


def _status(link: dict) -> str:
    if link.get("revoked_at"):
        return "revoked"
    if link["expires_at"] <= utc_now_iso():
        return "expired"
    return "active"


def _link_out(link: dict) -> dict:
    return {
        "id": link["_id"], "kind": link["kind"], "label": link["label"],
        "path": f"/api/share/{link['token']}",
        "created_at": link["created_at"], "expires_at": link["expires_at"],
        "status": _status(link), "open_count": link.get("open_count", 0),
        "last_opened_at": link.get("last_opened_at"),
    }


async def _params_for(ctx: dict, payload: ShareIn) -> tuple[dict, str]:
    agent_id = ctx["profile"]["_id"]
    db = get_db()
    if payload.kind == "quote":
        if not payload.package_id or not payload.pax:
            raise HTTPException(status_code=400, detail="package_id and pax are required")
        pkg, markup = await resolve_sellable_package(agent_id, payload.package_id, payload.pax)
        travel = parse_future_date(payload.travel_date)
        unit_retail = (money_from_bson(pkg["agent_cost"]) + markup).quantize(Decimal("0.01"))
        name = (payload.customer_name or "").strip() or None
        params = {
            "package_id": pkg["_id"], "pax": payload.pax, "unit_retail": str(unit_retail),
            "customer_name": name, "travel_label": travel.strftime("%d %b %Y") if travel else None,
            "quote_no": f"Q-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(2).upper()}",
            "issued_at": utc_now_iso(),
        }
        return params, f"Quote · {pkg['title']}" + (f" · {name}" if name else "")
    if not payload.booking_id:
        raise HTTPException(status_code=400, detail="booking_id is required")
    b = await _own_booking(agent_id, payload.booking_id)
    if payload.kind == "booking_quote":
        return {"booking_id": b["_id"]}, f"Quote · {b['reference_code']}"
    if not payload.payment_id:
        raise HTTPException(status_code=400, detail="payment_id is required")
    p = await db[Collections.BOOKING_PAYMENTS].find_one({"_id": payload.payment_id, "booking_id": b["_id"]})
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"booking_id": b["_id"], "payment_id": p["_id"]}, f"Receipt · {receipt_number(b, p)}"


@router.post("/api/agent/share-links")
async def create_link(payload: ShareIn, request: Request, ctx: dict = Depends(current_agent)):
    params, label = await _params_for(ctx, payload)
    now = datetime.now(timezone.utc)
    link = {
        "_id": secrets.token_hex(16), "token": secrets.token_urlsafe(24),
        "agent_id": ctx["profile"]["_id"], "kind": payload.kind, "label": label, "params": params,
        "expires_at": (now + timedelta(days=LINK_DAYS)).isoformat(), "revoked_at": None,
        "open_count": 0, "created_at": now.isoformat(), "updated_at": now.isoformat(),
    }
    await get_db()[Collections.SHARE_LINKS].insert_one(link)
    await _audit(ctx, "share_link.create", "share_link", link["_id"], None, {"kind": payload.kind, "label": label}, request)
    return {"link": _link_out(link)}


@router.get("/api/agent/share-links")
async def list_links(ctx: dict = Depends(current_agent)):
    rows = await get_db()[Collections.SHARE_LINKS].find({"agent_id": ctx["profile"]["_id"]}).sort("created_at", -1).to_list(length=200)
    return {"links": [_link_out(r) for r in rows]}


@router.post("/api/agent/share-links/{link_id}/revoke")
async def revoke_link(link_id: str, request: Request, ctx: dict = Depends(current_agent)):
    db = get_db()
    link = await db[Collections.SHARE_LINKS].find_one({"_id": link_id, "agent_id": ctx["profile"]["_id"]})
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    if not link.get("revoked_at"):
        now = utc_now_iso()
        await db[Collections.SHARE_LINKS].update_one({"_id": link_id}, {"$set": {"revoked_at": now, "updated_at": now}})
        link["revoked_at"] = now
        await _audit(ctx, "share_link.revoke", "share_link", link_id, None, {"label": link["label"]}, request)
    return {"link": _link_out(link)}


def _gone(message: str, code: int) -> HTMLResponse:
    html = (
        "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Link unavailable</title></head><body style='font-family:system-ui,sans-serif;"
        "display:flex;min-height:90vh;align-items:center;justify-content:center;color:#44403c;padding:24px'>"
        f"<div style='max-width:420px;text-align:center'><h2>Link unavailable</h2><p>{message}</p></div></body></html>"
    )
    return HTMLResponse(html, status_code=code)


@router.get("/api/share/{token}")
async def open_link(token: str):
    db = get_db()
    link = await db[Collections.SHARE_LINKS].find_one({"token": token})
    if not link:
        return _gone("This link doesn't exist. Please ask your travel agent for a new one.", 404)
    if _status(link) != "active":
        return _gone("This link has expired or was switched off. Please ask your travel agent for a new one.", 410)
    profile = await db[Collections.AGENT_PROFILES].find_one({"_id": link["agent_id"]})
    if not profile or profile.get("status") == "disabled":
        return _gone("This document is no longer available.", 410)
    user = await db[Collections.USERS].find_one({"_id": profile["user_id"]}, {"email": 1}) or {}
    email, params = user.get("email"), link["params"]
    try:
        if link["kind"] == "quote":
            pkg = await db[Collections.PACKAGES].find_one({"_id": params["package_id"]})
            if not pkg:
                return _gone("This package is no longer available.", 410)
            pdf = await render_quote(
                profile, email, pkg, Decimal(params["unit_retail"]), params["pax"], params.get("customer_name"),
                params.get("travel_label"), params["quote_no"], datetime.fromisoformat(params["issued_at"]),
            )
            filename = f"quote-{params['quote_no']}.pdf"
        else:
            b = await db[Collections.BOOKINGS].find_one({"_id": params["booking_id"], "agent_id": link["agent_id"]})
            if not b:
                return _gone("This booking is no longer available.", 410)
            if link["kind"] == "booking_quote":
                pdf = await render_booking_quote(profile, email, b)
                filename = f"quote-{b['reference_code']}.pdf"
            else:
                pdf, receipt_no = await render_receipt(profile, email, b, params["payment_id"])
                filename = f"receipt-{receipt_no}.pdf"
    except HTTPException:
        return _gone("This document is no longer available.", 410)
    now = utc_now_iso()
    await db[Collections.SHARE_LINKS].update_one({"_id": link["_id"]}, {"$inc": {"open_count": 1}, "$set": {"last_opened_at": now}})
    resp = pdf_response(pdf, filename, inline=True)
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp
