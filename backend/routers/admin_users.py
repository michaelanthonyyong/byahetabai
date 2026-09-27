"""Admin-only user/agent management under /api/admin/agents."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from core import auth_service
from core.db import Collections, get_db
from core.deps import require_role
from core.security import hash_password
from models.agent import AgentAccount, AgentProfile, AgentStatus
from models.audit_log import AuditLog
from models.base import utc_now_iso
from models.user import User, UserRole, UserStatus

router = APIRouter(prefix="/api/admin/agents", tags=["admin:agents"])

require_admin = require_role("admin")


# --- schemas -------------------------------------------------------------

class InviteAgentIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    agency_name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=40)


class AdminSetPasswordIn(BaseModel):
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class AgentOut(BaseModel):
    id: str
    user_id: str
    email: EmailStr
    display_name: str
    agency_name: Optional[str] = None
    phone: Optional[str] = None
    status: str
    created_at: str


def _agent_out(user: dict, profile: dict) -> AgentOut:
    return AgentOut(
        id=profile["_id"], user_id=user["_id"],
        email=user["email"], display_name=profile["display_name"],
        agency_name=profile.get("agency_name"), phone=profile.get("phone"),
        status=profile.get("status", "invited"),
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
async def list_agents(admin: dict = Depends(require_admin)):
    db = get_db()
    profiles = await db[Collections.AGENT_PROFILES].find({}).sort("created_at", -1).to_list(length=500)
    user_ids = [p["user_id"] for p in profiles]
    users = {u["_id"]: u async for u in db[Collections.USERS].find({"_id": {"$in": user_ids}})}
    return {
        "agents": [
            _agent_out(users[p["user_id"]], p).model_dump()
            for p in profiles if p["user_id"] in users
        ]
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
        password_hash=hash_password("!invited!" + user_random()),  # placeholder that cannot be used
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


def user_random() -> str:
    import secrets
    return secrets.token_urlsafe(16)
