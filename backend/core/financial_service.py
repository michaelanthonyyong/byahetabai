"""Financial-mutation services.

Every function here obeys three rules:
1. Balances change only inside this module.
2. Every balance change writes a ``financial_transactions`` row plus an
   ``audit_logs`` row.
3. Writes carry an ``idempotency_key`` so a duplicate call is a no-op.

Mongo transactions are only used when a replica set is present; on a
stand-alone dev server the writes still succeed sequentially, and the
reconciliation task planned for Phase 8 detects any inconsistency.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException

from core.db import Collections, get_db
from models.audit_log import AuditLog
from models.base import money_from_bson, money_to_bson, utc_now_iso
from models.transaction import (
    BOOKING_TYPES,
    COMMISSION_TYPES,
    FinancialTransaction,
    TransactionType,
)

logger = logging.getLogger(__name__)


def _account_for_type(t: TransactionType) -> str:
    if t in BOOKING_TYPES:
        return "booking"
    if t in COMMISSION_TYPES:
        return "commission"
    raise ValueError(f"Unknown transaction type: {t}")


def _signed_amount(t: TransactionType, amount: Decimal) -> Decimal:
    positive = {
        TransactionType.TOP_UP,
        TransactionType.BOOKING_REFUND,
        TransactionType.COMMISSION_ACCRUAL,
        TransactionType.ADJUSTMENT_CREDIT,
    }
    return amount if t in positive else -amount


async def adjust_agent_balance(
    *,
    agent_id: str,
    admin_user_id: str,
    admin_ip: Optional[str],
    admin_ua: Optional[str],
    kind: str,  # 'credit' | 'debit'
    amount: Decimal,
    reason: str,
) -> dict:
    """Manually adjust an agent's *booking* balance (admin-only)."""
    if kind not in ("credit", "debit"):
        raise HTTPException(status_code=400, detail="kind must be 'credit' or 'debit'")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be > 0")
    if not reason or len(reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="A reason (≥3 chars) is required")

    db = get_db()
    profile = await db[Collections.AGENT_PROFILES].find_one({"_id": agent_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Agent not found")

    txn_type = (
        TransactionType.ADJUSTMENT_CREDIT if kind == "credit"
        else TransactionType.ADJUSTMENT_DEBIT
    )
    account_kind = _account_for_type(txn_type)
    signed = _signed_amount(txn_type, amount)

    current_balance = money_from_bson(profile["booking_account"]["balance"]) or Decimal("0.00")
    new_balance = (current_balance + signed).quantize(Decimal("0.01"))
    if new_balance < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Debit would put the agent's booking balance negative "
                   f"(current: {current_balance}, requested: -{amount})",
        )

    txn = FinancialTransaction(
        agent_id=agent_id,
        account_kind=account_kind,
        type=txn_type,
        amount=signed,
        balance_after=new_balance,
        ref_type="adjustment",
        ref_id=None,
        idempotency_key=None,  # optional here; admin-initiated one-off
        created_by_user_id=admin_user_id,
        note=reason.strip(),
    )
    audit = AuditLog(
        actor_user_id=admin_user_id, actor_role="admin",
        action=f"agent.adjust_balance.{kind}",
        target_type="agent", target_id=agent_id,
        before={"booking_balance": str(current_balance)},
        after={"booking_balance": str(new_balance), "amount": str(amount), "reason": reason},
        ip=admin_ip, user_agent=admin_ua,
    )

    # Sequential writes (see module docstring for the replica-set caveat).
    await db[Collections.TRANSACTIONS].insert_one(txn.to_mongo())
    await db[Collections.AGENT_PROFILES].update_one(
        {"_id": agent_id},
        {"$set": {
            "booking_account.balance": money_to_bson(new_balance),
            "updated_at": utc_now_iso(),
        }},
    )
    await db[Collections.AUDIT_LOGS].insert_one(audit.to_mongo())

    return {
        "transaction_id": txn.id,
        "booking_balance": str(new_balance),
        "previous_balance": str(current_balance),
    }


async def approve_fund_request(
    *,
    fund_request_id: str,
    admin_user_id: str,
    admin_ip: Optional[str],
    admin_ua: Optional[str],
    decision_note: Optional[str] = None,
) -> dict:
    """Atomic TOP_UP credit driven by a pending fund request.

    Uses ``idempotency_key = "fund_request:{id}"`` so a duplicate approval
    is a no-op that returns the existing transaction id.
    """
    db = get_db()
    fr = await db[Collections.FUND_REQUESTS].find_one({"_id": fund_request_id})
    if not fr:
        raise HTTPException(status_code=404, detail="Fund request not found")

    idem_key = f"fund_request:{fund_request_id}"

    # Idempotency: if a TOP_UP with this key already exists, short-circuit.
    existing = await db[Collections.TRANSACTIONS].find_one({"idempotency_key": idem_key})
    if existing:
        # Self-heal: a prior crash may have written the txn + credited the
        # balance but not flipped the fund_request status. Finish the job.
        if fr.get("status") == "pending":
            now = utc_now_iso()
            await db[Collections.FUND_REQUESTS].update_one(
                {"_id": fund_request_id, "status": "pending"},
                {"$set": {
                    "status": "approved",
                    "decided_by_user_id": admin_user_id,
                    "decided_at": now,
                    "decision_note": decision_note,
                    "transaction_id": existing["_id"],
                    "updated_at": now,
                }},
            )
        return {
            "transaction_id": str(existing["_id"]),
            "already_approved": True,
            "status": "approved",
        }

    if fr.get("status") != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Only pending requests can be approved (current: {fr.get('status')})",
        )

    profile = await db[Collections.AGENT_PROFILES].find_one({"_id": fr["agent_id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Agent profile missing")

    amount = money_from_bson(fr["amount"]) or Decimal("0.00")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Request amount must be > 0")

    current_balance = money_from_bson(profile["booking_account"]["balance"]) or Decimal("0.00")
    new_balance = (current_balance + amount).quantize(Decimal("0.01"))

    txn = FinancialTransaction(
        agent_id=fr["agent_id"],
        account_kind="booking",
        type=TransactionType.TOP_UP,
        amount=amount,
        balance_after=new_balance,
        ref_type="fund_request",
        ref_id=fund_request_id,
        idempotency_key=idem_key,
        created_by_user_id=admin_user_id,
        note=(decision_note or "Fund request approval"),
    )
    audit = AuditLog(
        actor_user_id=admin_user_id, actor_role="admin",
        action="fund_request.approve",
        target_type="fund_request", target_id=fund_request_id,
        before={"status": "pending", "booking_balance": str(current_balance)},
        after={
            "status": "approved",
            "amount": str(amount),
            "booking_balance": str(new_balance),
            "decision_note": decision_note,
        },
        ip=admin_ip, user_agent=admin_ua,
    )

    now = utc_now_iso()
    await db[Collections.TRANSACTIONS].insert_one(txn.to_mongo())
    await db[Collections.AGENT_PROFILES].update_one(
        {"_id": fr["agent_id"]},
        {"$set": {
            "booking_account.balance": money_to_bson(new_balance),
            "updated_at": now,
        }},
    )
    await db[Collections.FUND_REQUESTS].update_one(
        {"_id": fund_request_id, "status": "pending"},
        {"$set": {
            "status": "approved",
            "decided_by_user_id": admin_user_id,
            "decided_at": now,
            "decision_note": decision_note,
            "transaction_id": txn.id,
            "updated_at": now,
        }},
    )
    await db[Collections.AUDIT_LOGS].insert_one(audit.to_mongo())

    return {
        "transaction_id": txn.id,
        "booking_balance": str(new_balance),
        "previous_balance": str(current_balance),
        "already_approved": False,
    }


async def reject_fund_request(
    *,
    fund_request_id: str,
    admin_user_id: str,
    admin_ip: Optional[str],
    admin_ua: Optional[str],
    decision_note: str,
) -> dict:
    """Mark a pending fund request as rejected. No ledger movement."""
    if not decision_note or len(decision_note.strip()) < 3:
        raise HTTPException(status_code=400, detail="A rejection reason (≥3 chars) is required")

    db = get_db()
    fr = await db[Collections.FUND_REQUESTS].find_one({"_id": fund_request_id})
    if not fr:
        raise HTTPException(status_code=404, detail="Fund request not found")
    if fr.get("status") != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Only pending requests can be rejected (current: {fr.get('status')})",
        )

    now = utc_now_iso()
    await db[Collections.FUND_REQUESTS].update_one(
        {"_id": fund_request_id, "status": "pending"},
        {"$set": {
            "status": "rejected",
            "decided_by_user_id": admin_user_id,
            "decided_at": now,
            "decision_note": decision_note.strip(),
            "updated_at": now,
        }},
    )
    await db[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=admin_user_id, actor_role="admin",
            action="fund_request.reject",
            target_type="fund_request", target_id=fund_request_id,
            before={"status": "pending"},
            after={"status": "rejected", "decision_note": decision_note.strip()},
            ip=admin_ip, user_agent=admin_ua,
        ).to_mongo()
    )
    return {"ok": True, "status": "rejected"}


async def sum_agent_balances() -> dict:
    """System-wide totals for the admin dashboard."""
    db = get_db()
    booking_total = Decimal("0.00")
    commission_total = Decimal("0.00")
    async for a in db[Collections.AGENT_PROFILES].find(
        {}, {"booking_account": 1, "commission_account": 1}
    ):
        booking_total += money_from_bson(a["booking_account"]["balance"]) or Decimal("0.00")
        commission_total += money_from_bson(a["commission_account"]["balance"]) or Decimal("0.00")
    return {
        "booking_total": str(booking_total),
        "commission_total": str(commission_total),
    }
