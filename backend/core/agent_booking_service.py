"""Agent-created bookings: atomic net-cost debit + markup snapshot."""
from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from bson.decimal128 import Decimal128
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core.db import Collections, get_db
from core.settings_service import get_markup_bounds
from models.audit_log import AuditLog
from models.base import money_from_bson, utc_now_iso
from models.booking import Booking, BookingStatus, BookingStatusHistoryEntry, BookingTraveler
from models.transaction import FinancialTransaction, TransactionType

CENT = Decimal("0.01")


def _new_reference() -> str:
    return f"BTB-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(2).upper()}"


def parse_future_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Travel date must be YYYY-MM-DD")
    if d < datetime.now(timezone.utc).date():
        raise HTTPException(status_code=400, detail="Travel date cannot be in the past")
    return d


async def resolve_sellable_package(agent_id: str, package_id: str, pax: int) -> tuple[dict, Decimal]:
    """Return (package, markup) or raise if the agent can't sell it."""
    db = get_db()
    pkg = await db[Collections.PACKAGES].find_one({"_id": package_id, "status": "published"})
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    m = await db[Collections.AGENT_PACKAGE_MARKUPS].find_one({"agent_id": agent_id, "package_id": package_id})
    lo, hi = await get_markup_bounds()
    markup = money_from_bson(m["markup_amount"]) if m else None
    if markup is None:
        raise HTTPException(status_code=400, detail="Set your markup on this package before selling it")
    if markup < lo or markup > hi:
        raise HTTPException(
            status_code=400,
            detail=f"Your markup is outside the allowed range (₱{lo}–₱{hi}). Update it first.",
        )
    if pax < pkg.get("min_pax", 1) or pax > pkg.get("max_pax", 99):
        raise HTTPException(
            status_code=400,
            detail=f"This package takes {pkg.get('min_pax', 1)}–{pkg.get('max_pax')} pax",
        )
    return pkg, markup


async def create_agent_booking(
    *, ctx: dict, customer_id: str, package_id: str, pax: int,
    travel_start_date: Optional[str], traveler_names: list[str], notes: Optional[str],
    ip: Optional[str], ua: Optional[str],
) -> dict:
    db = get_db()
    agent_id = ctx["profile"]["_id"]
    user_id = ctx["user"]["_id"]

    customer = await db[Collections.CUSTOMERS].find_one({"_id": customer_id, "agent_id": agent_id})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    pkg, markup = await resolve_sellable_package(agent_id, package_id, pax)
    start = parse_future_date(travel_start_date)
    if not start:
        raise HTTPException(status_code=400, detail="Travel date is required")
    end = start + timedelta(days=max(int(pkg.get("duration_days", 1)) - 1, 0))

    unit_net = money_from_bson(pkg["agent_cost"])
    unit_bonus = money_from_bson(pkg.get("commission_amount")) or Decimal("0.00")
    unit_retail = (unit_net + markup).quantize(CENT)
    total_net = (unit_net * pax).quantize(CENT)

    names = [n.strip() for n in traveler_names if n and n.strip()][:pax]
    if not names:
        names = [f"{customer['first_name']} {customer['last_name']}".strip()]
    travelers = [BookingTraveler(full_name=n[:120], is_lead=(i == 0)) for i, n in enumerate(names)]

    booking_id = str(uuid.uuid4())
    # Atomic, overdraft-proof debit of the net cost.
    profile = await db[Collections.AGENT_PROFILES].find_one_and_update(
        {"_id": agent_id, "booking_account.balance": {"$gte": Decimal128(total_net)}},
        {"$inc": {"booking_account.balance": Decimal128(-total_net)}, "$set": {"updated_at": utc_now_iso()}},
        return_document=ReturnDocument.AFTER,
    )
    if not profile:
        current = await db[Collections.AGENT_PROFILES].find_one({"_id": agent_id})
        bal = money_from_bson(current["booking_account"]["balance"])
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient booking balance (needed ₱{total_net}, available ₱{bal.quantize(CENT)}). Request a top-up first.",
        )
    new_balance = money_from_bson(profile["booking_account"]["balance"]).quantize(CENT)

    txn = FinancialTransaction(
        agent_id=agent_id, account_kind="booking", type=TransactionType.BOOKING_DEBIT,
        amount=-total_net, balance_after=new_balance,
        ref_type="booking", ref_id=booking_id,
        idempotency_key=f"booking_debit:{booking_id}",
        created_by_user_id=user_id,
        note=f"{pkg['title']} · {pax} pax",
    )
    try:
        await db[Collections.TRANSACTIONS].insert_one(txn.to_mongo())
        for _ in range(5):
            booking = Booking(
                id=booking_id, reference_code=_new_reference(),
                agent_id=agent_id, customer_id=customer_id, package_id=package_id, pax=pax,
                unit_agent_cost=unit_net, unit_guest_price=unit_retail, unit_commission_amount=unit_bonus,
                total_agent_cost=total_net, total_guest_price=(unit_retail * pax).quantize(CENT),
                total_commission_amount=(unit_bonus * pax).quantize(CENT),
                unit_markup_amount=markup, total_markup_amount=(markup * pax).quantize(CENT),
                total_retail_price=(unit_retail * pax).quantize(CENT),
                travel_start_date=start.isoformat(), travel_end_date=end.isoformat(),
                status=BookingStatus.PENDING,
                travelers=travelers,
                status_history=[BookingStatusHistoryEntry(
                    to_status=BookingStatus.PENDING, changed_by_user_id=user_id, note="Created by agent",
                )],
                notes=(notes or "").strip()[:1000] or None,
            )
            try:
                await db[Collections.BOOKINGS].insert_one(booking.to_mongo())
                break
            except DuplicateKeyError:
                continue
        else:
            raise HTTPException(status_code=500, detail="Could not allocate a booking reference")
    except Exception:
        # Compensate: return the debit so balance == SUM(ledger).
        await db[Collections.TRANSACTIONS].delete_one({"_id": txn.id})
        await db[Collections.AGENT_PROFILES].update_one(
            {"_id": agent_id}, {"$inc": {"booking_account.balance": Decimal128(total_net)}},
        )
        raise

    await db[Collections.AUDIT_LOGS].insert_one(AuditLog(
        actor_user_id=user_id, actor_role="agent", action="booking.create",
        target_type="booking", target_id=booking_id,
        before={"booking_balance": str((new_balance + total_net).quantize(CENT))},
        after={
            "reference_code": booking.reference_code, "package_id": package_id, "pax": pax,
            "total_agent_cost": str(total_net), "total_retail_price": str(booking.total_retail_price),
            "booking_balance": str(new_balance), "transaction_id": txn.id,
        },
        ip=ip, user_agent=ua,
    ).to_mongo())
    return await db[Collections.BOOKINGS].find_one({"_id": booking_id})
