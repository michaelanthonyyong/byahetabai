"""Booking lifecycle service.

Rules
-----
* Status transitions are validated against a small state machine.
* Cancelling a booking after it debited the agent may optionally refund it
  (writes BOOKING_REFUND to the ledger and returns the amount to the
  agent's booking account).
* If a commission had accrued (COMMISSION_ACCRUAL row for this booking)
  and the booking is cancelled, the accrual is reversed
  (COMMISSION_REVERSAL) and the ``commissions`` row is flipped to
  ``reversed`` — never left dangling.
* Every mutation writes an audit_logs entry.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException

from core.db import Collections, get_db
from models.audit_log import AuditLog
from models.base import money_from_bson, money_to_bson, utc_now_iso
from models.booking import BookingStatus, BookingStatusHistoryEntry, GuestPaymentStatus
from models.commission import CommissionStatus
from models.transaction import FinancialTransaction, TransactionType

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    BookingStatus.PENDING.value: {BookingStatus.CONFIRMED.value, BookingStatus.CANCELLED.value},
    BookingStatus.CONFIRMED.value: {BookingStatus.COMPLETED.value, BookingStatus.CANCELLED.value},
    BookingStatus.CANCELLED.value: set(),
    BookingStatus.COMPLETED.value: set(),
}


async def _write_audit(admin, action, target_id, before, after, ip, ua):
    await get_db()[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=admin["_id"], actor_role="admin",
            action=action, target_type="booking", target_id=target_id,
            before=before, after=after, ip=ip, user_agent=ua,
        ).to_mongo()
    )


async def change_status(
    *, booking_id: str, new_status: str, refund: bool,
    admin: dict, admin_ip: Optional[str], admin_ua: Optional[str],
    reason: Optional[str],
) -> dict:
    db = get_db()
    booking = await db[Collections.BOOKINGS].find_one({"_id": booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    old_status = booking["status"]
    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move booking from '{old_status}' to '{new_status}'",
        )

    history_entry = BookingStatusHistoryEntry(
        from_status=BookingStatus(old_status),
        to_status=BookingStatus(new_status),
        changed_by_user_id=admin["_id"],
        note=reason,
    ).model_dump(mode="python")

    update: dict = {
        "status": new_status,
        "updated_at": utc_now_iso(),
    }

    refund_txn_id: Optional[str] = None
    reversal_txn_id: Optional[str] = None

    # --- optional refund of booking balance ---
    if new_status == BookingStatus.CANCELLED.value and refund:
        total_agent_cost = money_from_bson(booking["total_agent_cost"]) or Decimal("0.00")
        if total_agent_cost > 0:
            profile = await db[Collections.AGENT_PROFILES].find_one({"_id": booking["agent_id"]})
            if not profile:
                raise HTTPException(status_code=500, detail="Agent profile missing for booking")
            cur = money_from_bson(profile["booking_account"]["balance"]) or Decimal("0.00")
            new_balance = (cur + total_agent_cost).quantize(Decimal("0.01"))
            refund_txn = FinancialTransaction(
                agent_id=booking["agent_id"], account_kind="booking",
                type=TransactionType.BOOKING_REFUND,
                amount=total_agent_cost,
                balance_after=new_balance,
                ref_type="booking", ref_id=booking["_id"],
                idempotency_key=f"refund-{booking['_id']}",
                created_by_user_id=admin["_id"],
                note=f"Refund on cancel: {reason or ''}",
            )
            await db[Collections.TRANSACTIONS].insert_one(refund_txn.to_mongo())
            await db[Collections.AGENT_PROFILES].update_one(
                {"_id": booking["agent_id"]},
                {"$set": {
                    "booking_account.balance": money_to_bson(new_balance),
                    "updated_at": utc_now_iso(),
                }},
            )
            refund_txn_id = refund_txn.id

    # --- reverse commission accrual on cancellation ---
    if new_status == BookingStatus.CANCELLED.value:
        commission = await db[Collections.COMMISSIONS].find_one(
            {"booking_id": booking["_id"], "status": CommissionStatus.ACCRUED.value}
        )
        if commission:
            profile = await db[Collections.AGENT_PROFILES].find_one({"_id": booking["agent_id"]})
            cur = money_from_bson(profile["commission_account"]["balance"]) or Decimal("0.00")
            amt = money_from_bson(commission["amount"]) or Decimal("0.00")
            new_commission_balance = (cur - amt).quantize(Decimal("0.01"))
            reversal_txn = FinancialTransaction(
                agent_id=booking["agent_id"], account_kind="commission",
                type=TransactionType.COMMISSION_REVERSAL,
                amount=-amt,
                balance_after=new_commission_balance,
                ref_type="booking", ref_id=booking["_id"],
                idempotency_key=f"reversal-{commission['_id']}",
                created_by_user_id=admin["_id"],
                note=f"Reversal on cancel: {reason or ''}",
            )
            await db[Collections.TRANSACTIONS].insert_one(reversal_txn.to_mongo())
            await db[Collections.AGENT_PROFILES].update_one(
                {"_id": booking["agent_id"]},
                {"$set": {
                    "commission_account.balance": money_to_bson(new_commission_balance),
                    "updated_at": utc_now_iso(),
                }},
            )
            await db[Collections.COMMISSIONS].update_one(
                {"_id": commission["_id"]},
                {"$set": {
                    "status": CommissionStatus.REVERSED.value,
                    "reversal_transaction_id": reversal_txn.id,
                    "updated_at": utc_now_iso(),
                }},
            )
            reversal_txn_id = reversal_txn.id

    await db[Collections.BOOKINGS].update_one(
        {"_id": booking_id},
        {"$set": update, "$push": {"status_history": history_entry}},
    )
    await _write_audit(
        admin, f"booking.status.{new_status}", booking_id,
        {"status": old_status},
        {
            "status": new_status,
            "reason": reason,
            "refund_transaction_id": refund_txn_id,
            "commission_reversal_transaction_id": reversal_txn_id,
        },
        admin_ip, admin_ua,
    )
    return {
        "status": new_status,
        "refund_transaction_id": refund_txn_id,
        "commission_reversal_transaction_id": reversal_txn_id,
    }


async def set_guest_payment_status(
    *, booking_id: str, new_gps: str, admin: dict,
    admin_ip: Optional[str], admin_ua: Optional[str], note: Optional[str],
) -> dict:
    """Update the informational guest-payment status. No ledger impact."""
    if new_gps not in {s.value for s in GuestPaymentStatus}:
        raise HTTPException(status_code=400, detail="Invalid guest payment status")
    db = get_db()
    booking = await db[Collections.BOOKINGS].find_one({"_id": booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    old = booking.get("guest_payment_status")
    if old == new_gps:
        return {"ok": True, "changed": False}
    await db[Collections.BOOKINGS].update_one(
        {"_id": booking_id},
        {"$set": {"guest_payment_status": new_gps, "updated_at": utc_now_iso()}},
    )
    await _write_audit(
        admin, "booking.guest_payment_status", booking_id,
        {"guest_payment_status": old},
        {"guest_payment_status": new_gps, "note": note},
        admin_ip, admin_ua,
    )
    return {"ok": True, "changed": True}
