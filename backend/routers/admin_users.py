"""Admin-only user/agent management under /api/admin/agents."""
from __future__ import annotations

import re
import secrets
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from core import auth_service
from core.db import Collections, get_db
from core.deps import require_role
from core.financial_service import adjust_agent_balance
from core.security import hash_password
from models.agent import AgentAccount, AgentProfile, AgentStatus
from models.audit_log import AuditLog
from models.base import money_from_bson, utc_now_iso
from models.user import User, UserRole, UserStatus

router = APIRouter(prefix="/api/admin/agents", tags=["admin:agents"])

require_admin = require_role("admin")


def _random_placeholder_password() -> str:
    """Cryptographic filler for the INVITED user's password_hash slot.

    Never used to authenticate — the invite-acceptance flow always overwrites
    it before status flips to active.
    """
    return "!invited!" + secrets.token_urlsafe(16)


# --- schemas -------------------------------------------------------------

class InviteAgentIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    agency_name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=40)


class AdminSetPasswordIn(BaseModel):
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class AgentUpdateIn(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    agency_name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=400)


class AdjustBalanceIn(BaseModel):
    kind: str = Field(pattern="^(credit|debit)$")
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=3, max_length=400)


class AgentOut(BaseModel):
    id: str
    user_id: str
    email: EmailStr
    display_name: str
    agency_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: str
    booking_balance: str
    commission_balance: str
    currency: str = "PHP"
    last_login_at: Optional[str] = None
    created_at: str


def _agent_out(user: dict, profile: dict) -> AgentOut:
    booking = money_from_bson(profile.get("booking_account", {}).get("balance")) or Decimal("0.00")
    commission = money_from_bson(profile.get("commission_account", {}).get("balance")) or Decimal("0.00")
    return AgentOut(
        id=profile["_id"], user_id=user["_id"],
        email=user["email"], display_name=profile["display_name"],
        agency_name=profile.get("agency_name"), phone=profile.get("phone"),
        address=profile.get("address"),
        status=profile.get("status", "invited"),
        booking_balance=str(booking),
        commission_balance=str(commission),
        last_login_at=user.get("last_login_at"),
        created_at=profile["created_at"],
    )


async def _write_audit(admin: dict, action: str, target_id: str, before: Optional[dict], after: Optional[dict], request: Request) -> None:
    await get_db()[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=admin["_id"], actor_role="admin",
            action=action, target_type="agent", target_id=target_id,
            before=before, after=after,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        ).to_mongo()
    )


# --- endpoints -----------------------------------------------------------

@router.get("")
async def list_agents(
    admin: dict = Depends(require_admin),
    status: Optional[str] = Query(default=None, pattern="^(active|invited|disabled)$"),
    q: Optional[str] = Query(default=None, description="search email / display / agency"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    db = get_db()
    pquery: dict = {}
    if status:
        pquery["status"] = status

    # Search — resolve to a matching user_id set when needed.
    if q:
        pattern = re.escape(q.strip())
        rx = {"$regex": pattern, "$options": "i"}
        # Find user_ids where email matches; also filter profile fields directly.
        matching_user_ids = [
            u["_id"] async for u in db[Collections.USERS].find({"email": rx}, {"_id": 1})
        ]
        pquery["$or"] = [
            {"display_name": rx},
            {"agency_name": rx},
            {"user_id": {"$in": matching_user_ids}},
        ]

    total = await db[Collections.AGENT_PROFILES].count_documents(pquery)
    profiles = await (
        db[Collections.AGENT_PROFILES].find(pquery).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )
    user_ids = [p["user_id"] for p in profiles]
    users = {u["_id"]: u async for u in db[Collections.USERS].find({"_id": {"$in": user_ids}})}
    return {
        "agents": [
            _agent_out(users[p["user_id"]], p).model_dump()
            for p in profiles if p["user_id"] in users
        ],
        "page": page, "page_size": page_size, "total": total,
    }


@router.post("")
async def invite_agent(
    payload: InviteAgentIn, request: Request, admin: dict = Depends(require_admin)
):
    db = get_db()
    email = payload.email.lower().strip()
    if await db[Collections.USERS].find_one({"email": email}):
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    # Create the user (INVITED — cannot log in until they accept).
    user = User(
        email=email,
        password_hash=hash_password(_random_placeholder_password()),
        role=UserRole.AGENT,
        status=UserStatus.INVITED,
        display_name=payload.display_name,
        created_by_user_id=admin["_id"],
    )
    profile = AgentProfile(
        user_id=user.id,
        display_name=payload.display_name,
        agency_name=payload.agency_name,
        phone=payload.phone,
        status=AgentStatus.INVITED,
        booking_account=AgentAccount(kind="booking"),
        commission_account=AgentAccount(kind="commission"),
        created_by_user_id=admin["_id"],
    )
    await db[Collections.USERS].insert_one(user.to_mongo())
    await db[Collections.AGENT_PROFILES].insert_one(profile.to_mongo())
    raw_token = await auth_service.issue_invite_token(user.id, admin["_id"])
    await _write_audit(
        admin, "agent.invite", profile.id, None,
        {"email": email, "display_name": payload.display_name}, request,
    )
    return {
        "agent": _agent_out(user.to_mongo(), profile.to_mongo()).model_dump(),
        "invite_token": raw_token,
        "invite_path": f"/accept-invite?token={raw_token}",
    }


@router.post("/{agent_id}/reset-password")
async def admin_reset_password(
    agent_id: str, payload: AdminSetPasswordIn,
    request: Request, admin: dict = Depends(require_admin),
):
    db = get_db()
    profile = await db[Collections.AGENT_PROFILES].find_one({"_id": agent_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Agent not found")

    if payload.new_password:
        await db[Collections.USERS].update_one(
            {"_id": profile["user_id"]},
            {"$set": {
                "password_hash": hash_password(payload.new_password),
                "updated_at": utc_now_iso(),
            }},
        )
        await _write_audit(
            admin, "agent.password_set_directly", agent_id, None,
            {"agent_id": agent_id}, request,
        )
        return {"ok": True, "mode": "direct"}

    raw_token = await auth_service.issue_reset_token(profile["user_id"], admin["_id"])
    await _write_audit(
        admin, "agent.password_reset_token_issued", agent_id, None,
        {"agent_id": agent_id}, request,
    )
    return {
        "ok": True, "mode": "token",
        "reset_token": raw_token,
        "reset_path": f"/reset-password?token={raw_token}",
    }


class UpdateAgentStatusIn(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")


@router.patch("/{agent_id}/status")
async def set_agent_status(
    agent_id: str, payload: UpdateAgentStatusIn,
    request: Request, admin: dict = Depends(require_admin),
):
    db = get_db()
    profile = await db[Collections.AGENT_PROFILES].find_one({"_id": agent_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Agent not found")
    before = {"status": profile.get("status")}
    await db[Collections.AGENT_PROFILES].update_one(
        {"_id": agent_id}, {"$set": {"status": payload.status, "updated_at": utc_now_iso()}}
    )
    await db[Collections.USERS].update_one(
        {"_id": profile["user_id"]},
        {"$set": {"status": payload.status, "updated_at": utc_now_iso()}},
    )
    await _write_audit(admin, "agent.status_change", agent_id, before, {"status": payload.status}, request)
    return {"ok": True}


# --- detail / update / adjust-balance / transactions --------------------

@router.get("/{agent_id}")
async def get_agent(agent_id: str, admin: dict = Depends(require_admin)):
    db = get_db()
    profile = await db[Collections.AGENT_PROFILES].find_one({"_id": agent_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Agent not found")
    user = await db[Collections.USERS].find_one({"_id": profile["user_id"]})
    if not user:
        raise HTTPException(status_code=404, detail="Linked user missing")
    return {"agent": _agent_out(user, profile).model_dump()}


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str, payload: AgentUpdateIn, request: Request,
    admin: dict = Depends(require_admin),
):
    db = get_db()
    profile = await db[Collections.AGENT_PROFILES].find_one({"_id": agent_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Agent not found")

    updates: dict[str, Any] = {"updated_at": utc_now_iso()}
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for field in ("display_name", "agency_name", "phone", "address"):
        val = getattr(payload, field)
        if val is not None and val != profile.get(field):
            updates[field] = val
            before[field] = profile.get(field)
            after[field] = val

    if not after:
        return {"ok": True, "changed": False}

    await db[Collections.AGENT_PROFILES].update_one({"_id": agent_id}, {"$set": updates})
    if "display_name" in after:
        await db[Collections.USERS].update_one(
            {"_id": profile["user_id"]},
            {"$set": {"display_name": after["display_name"], "updated_at": utc_now_iso()}},
        )
    await _write_audit(admin, "agent.update", agent_id, before, after, request)
    return {"ok": True, "changed": True, "fields": list(after.keys())}


@router.post("/{agent_id}/adjust-balance")
async def adjust_balance(
    agent_id: str, payload: AdjustBalanceIn, request: Request,
    admin: dict = Depends(require_admin),
):
    result = await adjust_agent_balance(
        agent_id=agent_id,
        admin_user_id=admin["_id"],
        admin_ip=(request.client.host if request.client else None),
        admin_ua=request.headers.get("user-agent"),
        kind=payload.kind,
        amount=payload.amount,
        reason=payload.reason,
    )
    return {"ok": True, **result}


@router.get("/{agent_id}/transactions")
async def list_agent_transactions(
    agent_id: str,
    admin: dict = Depends(require_admin),
    account_kind: Optional[str] = Query(default=None, pattern="^(booking|commission)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    db = get_db()
    profile = await db[Collections.AGENT_PROFILES].find_one({"_id": agent_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Agent not found")
    q: dict = {"agent_id": agent_id}
    if account_kind:
        q["account_kind"] = account_kind
    total = await db[Collections.TRANSACTIONS].count_documents(q)
    rows = await (
        db[Collections.TRANSACTIONS].find(q).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )
    txns = []
    for r in rows:
        r["id"] = r.pop("_id")
        r["amount"] = str(money_from_bson(r["amount"]))
        r["balance_after"] = str(money_from_bson(r["balance_after"]))
        txns.append(r)
    return {"transactions": txns, "page": page, "page_size": page_size, "total": total}


@router.get("/{agent_id}/audit-logs")
async def list_agent_audit(
    agent_id: str,
    admin: dict = Depends(require_admin),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    db = get_db()
    q = {"target_type": "agent", "target_id": agent_id}
    total = await db[Collections.AUDIT_LOGS].count_documents(q)
    rows = await (
        db[Collections.AUDIT_LOGS].find(q).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )
    logs = []
    for r in rows:
        r["id"] = r.pop("_id")
        logs.append(r)
    return {
        "audit_logs": logs,
        "page": page, "page_size": page_size, "total": total,
    }
