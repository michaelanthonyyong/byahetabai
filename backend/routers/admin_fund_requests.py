"""Admin-only fund-request queue under /api/admin/fund-requests.

Business rules
--------------
* An admin approves a pending request → single atomic TOP_UP (see
  ``financial_service.approve_fund_request``).  Idempotency key is
  ``fund_request:{id}`` so re-clicking the button never double-credits.
* An admin rejects a pending request → status flip + audit log; no ledger.
* Admin may also file a request **on behalf of** an agent so the queue is
  usable before the agent portal (Phase 5) ships.  Those land in ``pending``.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.db import Collections, get_db
from core.deps import require_role
from core.financial_service import approve_fund_request, reject_fund_request
from core.settings_service import get_topup_bounds
from models.audit_log import AuditLog
from models.base import money_from_bson, utc_now_iso
from models.fund_request import FundRequest, FundRequestStatus

router = APIRouter(prefix="/api/admin/fund-requests", tags=["admin:fund-requests"])

require_admin = require_role("admin")


# --- schemas -------------------------------------------------------------

class CreateFundRequestIn(BaseModel):
    agent_id: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    reference_no: Optional[str] = Field(default=None, max_length=120)
    note: Optional[str] = Field(default=None, max_length=400)


class ApproveIn(BaseModel):
    decision_note: Optional[str] = Field(default=None, max_length=400)


class RejectIn(BaseModel):
    decision_note: str = Field(min_length=3, max_length=400)


# --- helpers -------------------------------------------------------------

def _fr_row(fr: dict, agent: Optional[dict]) -> dict:
    return {
        "id": fr["_id"],
        "agent_id": fr["agent_id"],
        "agent": (
            {
                "id": agent["_id"],
                "display_name": agent.get("display_name"),
                "agency_name": agent.get("agency_name"),
            }
            if agent else None
        ),
        "amount": str(money_from_bson(fr["amount"])),
        "currency": fr.get("currency", "PHP"),
        "reference_no": fr.get("reference_no"),
        "note": fr.get("note"),
        "status": fr.get("status"),
        "decided_by_user_id": fr.get("decided_by_user_id"),
        "decided_at": fr.get("decided_at"),
        "decision_note": fr.get("decision_note"),
        "transaction_id": fr.get("transaction_id"),
        "created_at": fr.get("created_at"),
        "updated_at": fr.get("updated_at"),
    }


async def _write_audit(admin: dict, action: str, target_id: str, before, after, request: Request):
    await get_db()[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=admin["_id"], actor_role="admin",
            action=action, target_type="fund_request", target_id=target_id,
            before=before, after=after,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        ).to_mongo()
    )


# --- endpoints -----------------------------------------------------------

@router.get("")
async def list_fund_requests(
    admin: dict = Depends(require_admin),
    status: Optional[str] = Query(default=None, pattern="^(pending|approved|rejected)$"),
    agent_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    db = get_db()
    q: dict = {}
    if status:
        q["status"] = status
    if agent_id:
        q["agent_id"] = agent_id

    total = await db[Collections.FUND_REQUESTS].count_documents(q)
    rows = await (
        db[Collections.FUND_REQUESTS].find(q).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )
    agent_ids = list({r["agent_id"] for r in rows})
    agents = {
        a["_id"]: a async for a in db[Collections.AGENT_PROFILES].find({"_id": {"$in": agent_ids}})
    }
    pending_count = await db[Collections.FUND_REQUESTS].count_documents({"status": "pending"})
    return {
        "fund_requests": [_fr_row(r, agents.get(r["agent_id"])) for r in rows],
        "page": page, "page_size": page_size, "total": total,
        "pending_count": pending_count,
    }


@router.get("/{fund_request_id}")
async def get_fund_request(fund_request_id: str, admin: dict = Depends(require_admin)):
    db = get_db()
    fr = await db[Collections.FUND_REQUESTS].find_one({"_id": fund_request_id})
    if not fr:
        raise HTTPException(status_code=404, detail="Fund request not found")
    agent = await db[Collections.AGENT_PROFILES].find_one({"_id": fr["agent_id"]})

    txn = None
    if fr.get("transaction_id"):
        t = await db[Collections.TRANSACTIONS].find_one({"_id": fr["transaction_id"]})
        if t:
            txn = {
                "id": t["_id"],
                "type": t.get("type"),
                "amount": str(money_from_bson(t["amount"])),
                "balance_after": str(money_from_bson(t["balance_after"])),
                "created_at": t.get("created_at"),
            }
    return {"fund_request": _fr_row(fr, agent), "transaction": txn}


@router.post("")
async def create_fund_request_on_behalf(
    payload: CreateFundRequestIn, request: Request,
    admin: dict = Depends(require_admin),
):
    """Admin files a pending fund request on behalf of an agent.

    Lands in ``pending`` so the approval flow is still exercised.
    """
    min_amount, max_amount = await get_topup_bounds()
    if payload.amount < min_amount or payload.amount > max_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Amount must be between ₱{min_amount} and ₱{max_amount}",
        )
    db = get_db()
    profile = await db[Collections.AGENT_PROFILES].find_one({"_id": payload.agent_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Agent not found")
    if profile.get("status") == "disabled":
        raise HTTPException(status_code=400, detail="Agent is disabled")

    fr = FundRequest(
        agent_id=payload.agent_id,
        amount=payload.amount,
        reference_no=(payload.reference_no or None),
        note=(payload.note or None),
        status=FundRequestStatus.PENDING,
    )
    await db[Collections.FUND_REQUESTS].insert_one(fr.to_mongo())
    await _write_audit(
        admin, "fund_request.create_on_behalf", fr.id,
        before=None,
        after={
            "agent_id": payload.agent_id,
            "amount": str(payload.amount),
            "reference_no": payload.reference_no,
        },
        request=request,
    )
    return {"fund_request": _fr_row(fr.to_mongo(), profile)}


@router.post("/{fund_request_id}/approve")
async def approve(
    fund_request_id: str, payload: ApproveIn, request: Request,
    admin: dict = Depends(require_admin),
):
    result = await approve_fund_request(
        fund_request_id=fund_request_id,
        admin_user_id=admin["_id"],
        admin_ip=(request.client.host if request.client else None),
        admin_ua=request.headers.get("user-agent"),
        decision_note=payload.decision_note,
    )
    return {"ok": True, **result}


@router.post("/{fund_request_id}/reject")
async def reject(
    fund_request_id: str, payload: RejectIn, request: Request,
    admin: dict = Depends(require_admin),
):
    result = await reject_fund_request(
        fund_request_id=fund_request_id,
        admin_user_id=admin["_id"],
        admin_ip=(request.client.host if request.client else None),
        admin_ua=request.headers.get("user-agent"),
        decision_note=payload.decision_note,
    )
    return result
