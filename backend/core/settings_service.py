"""Typed access to the ``system_settings`` collection.

The Settings page (Admin Portal) is a *controlled* editor — only the keys
declared in ``SETTINGS_SCHEMA`` can be read/written, and each value is
validated by the schema before being persisted.  Every write emits an audit
log via the caller.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException

from .db import Collections, get_db
from models.base import utc_now_iso


# --- Validation helpers --------------------------------------------------

def _validate_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.lower() in ("true", "false"):
        return v.lower() == "true"
    raise HTTPException(status_code=400, detail="Expected a boolean")


def _validate_money(v: Any, *, min_v: Decimal, max_v: Decimal) -> str:
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=400, detail="Expected a decimal amount")
    if d < min_v or d > max_v:
        raise HTTPException(
            status_code=400,
            detail=f"Amount must be between ₱{min_v} and ₱{max_v}",
        )
    return str(d.quantize(Decimal("0.01")))


def _validate_brand(v: Any) -> dict:
    if not isinstance(v, dict):
        raise HTTPException(status_code=400, detail="Brand must be an object")
    allowed = {"name", "tagline", "currency", "support_email", "support_phone"}
    out: dict[str, str] = {}
    for k in allowed:
        val = v.get(k, "")
        if val is None:
            val = ""
        if not isinstance(val, str):
            raise HTTPException(status_code=400, detail=f"brand.{k} must be a string")
        if k == "name" and not val.strip():
            raise HTTPException(status_code=400, detail="brand.name is required")
        out[k] = val.strip()[:200]
    return out


# --- Schema -------------------------------------------------------------

SETTINGS_SCHEMA: dict[str, dict[str, Any]] = {
    "brand": {
        "label": "Brand & business info",
        "kind": "object",
        "description": "Displayed on the public site and in emails.",
        "validate": _validate_brand,
    },
    "minimum_topup_amount": {
        "label": "Minimum top-up amount (PHP)",
        "kind": "money",
        "description": "Floor for every agent fund request.",
        "validate": lambda v: _validate_money(v, min_v=Decimal("1"), max_v=Decimal("1000000")),
    },
    "maximum_topup_amount": {
        "label": "Maximum top-up amount (PHP)",
        "kind": "money",
        "description": "Ceiling for every agent fund request.",
        "validate": lambda v: _validate_money(v, min_v=Decimal("1"), max_v=Decimal("10000000")),
    },
    "commission_withdrawals_enabled": {
        "label": "Commission withdrawals enabled",
        "kind": "bool",
        "description": "Master switch for the agent commission withdrawal flow (Phase 7).",
        "validate": _validate_bool,
    },
}


# --- Access helpers -----------------------------------------------------

async def get_setting(key: str, default: Any = None) -> Any:
    row = await get_db()[Collections.SETTINGS].find_one({"key": key})
    if not row:
        return default
    return row.get("value", default)


async def get_all_settings() -> dict[str, Any]:
    """Return every schema-declared setting with its current value."""
    db = get_db()
    keys = list(SETTINGS_SCHEMA.keys())
    rows = {
        r["key"]: r
        async for r in db[Collections.SETTINGS].find({"key": {"$in": keys}})
    }
    return {
        k: {
            "key": k,
            "label": meta["label"],
            "kind": meta["kind"],
            "description": meta["description"],
            "value": rows.get(k, {}).get("value"),
            "updated_at": rows.get(k, {}).get("updated_at"),
        }
        for k, meta in SETTINGS_SCHEMA.items()
    }


async def update_setting(key: str, value: Any) -> dict:
    """Validate and persist a single setting. Returns before/after."""
    meta = SETTINGS_SCHEMA.get(key)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")
    validated = meta["validate"](value)

    # Cross-key rule: max ≥ min.
    if key == "minimum_topup_amount":
        current_max = await get_setting("maximum_topup_amount", "1000000.00")
        if Decimal(str(validated)) > Decimal(str(current_max)):
            raise HTTPException(
                status_code=400,
                detail=f"Minimum ({validated}) cannot exceed current maximum ({current_max})",
            )
    if key == "maximum_topup_amount":
        current_min = await get_setting("minimum_topup_amount", "100.00")
        if Decimal(str(validated)) < Decimal(str(current_min)):
            raise HTTPException(
                status_code=400,
                detail=f"Maximum ({validated}) cannot be below current minimum ({current_min})",
            )

    db = get_db()
    existing = await db[Collections.SETTINGS].find_one({"key": key})
    before = existing.get("value") if existing else None
    now = utc_now_iso()
    if existing:
        await db[Collections.SETTINGS].update_one(
            {"key": key},
            {"$set": {"value": validated, "updated_at": now}},
        )
    else:
        import uuid
        new_id = str(uuid.uuid4())
        await db[Collections.SETTINGS].insert_one({
            "_id": new_id,
            "id": new_id,
            "key": key,
            "value": validated,
            "description": meta["description"],
            "created_at": now,
            "updated_at": now,
        })
    return {"key": key, "before": before, "after": validated}


async def get_topup_bounds() -> tuple[Decimal, Decimal]:
    min_v = Decimal(str(await get_setting("minimum_topup_amount", "100.00")))
    max_v = Decimal(str(await get_setting("maximum_topup_amount", "1000000.00")))
    return min_v, max_v
