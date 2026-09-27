"""Admin-only controlled Settings editor.

Only the keys declared in ``settings_service.SETTINGS_SCHEMA`` are visible
and writable via this API.  Every change is validated and audit-logged.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core.db import Collections, get_db
from core.deps import require_role
from core.settings_service import SETTINGS_SCHEMA, get_all_settings, update_setting
from models.audit_log import AuditLog

router = APIRouter(prefix="/api/admin/settings", tags=["admin:settings"])

require_admin = require_role("admin")


class UpdateSettingIn(BaseModel):
    value: Any = Field(description="New value; validated per key schema")


@router.get("")
async def list_settings(admin: dict = Depends(require_admin)):
    return {"settings": await get_all_settings()}


@router.put("/{key}")
async def put_setting(
    key: str, payload: UpdateSettingIn, request: Request,
    admin: dict = Depends(require_admin),
):
    if key not in SETTINGS_SCHEMA:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")

    result = await update_setting(key, payload.value)

    await get_db()[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=admin["_id"], actor_role="admin",
            action="settings.update",
            target_type="setting", target_id=key,
            before={"value": result["before"]},
            after={"value": result["after"]},
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        ).to_mongo()
    )
    return {"ok": True, **result}
