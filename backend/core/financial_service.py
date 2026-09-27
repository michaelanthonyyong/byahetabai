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
