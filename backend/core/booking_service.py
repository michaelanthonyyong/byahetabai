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
from pymongo import ReturnDocument

from core.db import Collections, get_db
from core.notification_service import notify_agent
from models.audit_log import AuditLog
from models.base import money_from_bson, money_to_bson, utc_now_iso
from models.booking import BookingStatus, BookingStatusHistoryEntry
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
            profile = await db[Collections.AGENT_PROFILES].find_one_and_update(
                {"_id": booking["agent_id"]},
                {"$inc": {"booking_account.balance": money_to_bson(total_agent_cost)},
                 "$set": {"updated_at": utc_now_iso()}},
                return_document=ReturnDocument.AFTER,
            )
            if not profile:
                raise HTTPException(status_code=500, detail="Agent profile missing for booking")
            new_balance = money_from_bson(profile["booking_account"]["balance"]).quantize(Decimal("0.01"))
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
            refund_txn_id = refund_txn.id

    # --- reverse commission accrual on cancellation ---
    if new_status == BookingStatus.CANCELLED.value:
        commission = await db[Collections.COMMISSIONS].find_one(
            {"booking_id": booking["_id"], "status": CommissionStatus.ACCRUED.value}
        )
        if commission:
            amt = money_from_bson(commission["amount"]) or Decimal("0.00")
            profile = await db[Collections.AGENT_PROFILES].find_one_and_update(
                {"_id": booking["agent_id"]},
                {"$inc": {"commission_account.balance": money_to_bson(-amt)},
                 "$set": {"updated_at": utc_now_iso()}},
                return_document=ReturnDocument.AFTER,
            )
            new_commission_balance = money_from_bson(profile["commission_account"]["balance"]).quantize(Decimal("0.01"))
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
    await _notify_status(booking, new_status, refund_txn_id, reason)
    return {
        "status": new_status,
        "refund_transaction_id": refund_txn_id,
        "commission_reversal_transaction_id": reversal_txn_id,
    }


async def _notify_status(booking: dict, new_status: str, refunded: Optional[str], reason: Optional[str]) -> None:
    pkg = await get_db()[Collections.PACKAGES].find_one({"_id": booking["package_id"]}, {"title": 1})
    label = f"{booking['reference_code']} · {(pkg or {}).get('title', 'Package')}"
    if new_status == BookingStatus.CONFIRMED.value:
        title, body = "Booking confirmed", f"{label} is confirmed."
    elif new_status == BookingStatus.COMPLETED.value:
        title, body = "Trip completed", f"{label} is marked completed."
    elif new_status == BookingStatus.CANCELLED.value:
        amt = money_from_bson(booking["total_agent_cost"]) or Decimal("0.00")
        refund_text = f" ₱{amt:,.2f} was refunded to your booking balance." if refunded else " No refund was issued."
        title, body = "Booking cancelled", f"{label} was cancelled.{refund_text}" + (f" Reason: {reason}" if reason else "")
    else:
        return
    await notify_agent(
        agent_id=booking["agent_id"], kind=f"booking.{new_status}", title=title, body=body,
        ref_type="booking", ref_id=booking["_id"],
    )
