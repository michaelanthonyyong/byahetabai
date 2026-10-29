"""Customer payments recorded by agents; drives booking.guest_payment_status."""
from __future__ import annotations

from decimal import Decimal

from core.db import Collections, get_db
from models.base import money_from_bson, utc_now_iso

ZERO = Decimal("0.00")


def booking_total_due(b: dict) -> Decimal:
    v = b.get("total_retail_price")
    if v is None:
        v = b.get("total_guest_price")
    return money_from_bson(v) or ZERO


async def payments_total(booking_id: str) -> Decimal:
    total = ZERO
    async for p in get_db()[Collections.BOOKING_PAYMENTS].find({"booking_id": booking_id}, {"amount": 1}):
        total += money_from_bson(p["amount"]) or ZERO
    return total.quantize(Decimal("0.01"))


async def paid_totals(booking_ids: list[str]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    async for p in get_db()[Collections.BOOKING_PAYMENTS].find({"booking_id": {"$in": booking_ids}}, {"booking_id": 1, "amount": 1}):
        out[p["booking_id"]] = out.get(p["booking_id"], ZERO) + (money_from_bson(p["amount"]) or ZERO)
    return out


def derive_status(paid: Decimal, due: Decimal) -> str:
    if paid <= 0:
        return "unpaid"
    return "paid" if paid >= due else "partial"


async def sync_payment_status(booking: dict) -> str:
    paid = await payments_total(booking["_id"])
    status = derive_status(paid, booking_total_due(booking))
    if status != booking.get("guest_payment_status"):
        await get_db()[Collections.BOOKINGS].update_one(
            {"_id": booking["_id"]},
            {"$set": {"guest_payment_status": status, "updated_at": utc_now_iso()}},
        )
    return status
