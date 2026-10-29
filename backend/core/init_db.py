"""Idempotent database initialisation.

Called on FastAPI startup and by the verification script.  Safe to run
repeatedly against an existing database.

Responsibilities
----------------
1. Ensure every canonical collection exists (Mongo creates lazily, but we
   materialise them so listings look correct in tools).
2. Create indexes (unique + query-support).  ``create_index`` is
   idempotent; re-running with the same spec is a no-op.
3. Ensure a minimal set of ``system_settings`` rows exists.
"""
from __future__ import annotations

import logging
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel

from .db import Collections, get_db
from models.base import utc_now_iso

logger = logging.getLogger(__name__)


# --- Index catalogue -------------------------------------------------------
# One entry per collection.  Each tuple is (keys, kwargs-for-IndexModel).
INDEXES: dict[str, list[tuple[list, dict[str, Any]]]] = {
    Collections.USERS: [
        ([("email", ASCENDING)], {"unique": True, "name": "uniq_email"}),
        ([("role", ASCENDING), ("status", ASCENDING)], {"name": "role_status"}),
    ],
    Collections.AGENT_PROFILES: [
        ([("user_id", ASCENDING)], {"unique": True, "name": "uniq_user_id"}),
        ([("status", ASCENDING)], {"name": "status"}),
    ],
    Collections.DESTINATIONS: [
        ([("slug", ASCENDING)], {"unique": True, "name": "uniq_slug"}),
        ([("scope", ASCENDING), ("is_active", ASCENDING)], {"name": "scope_active"}),
        ([("featured_on_home", ASCENDING)], {"name": "featured"}),
    ],
    Collections.PACKAGES: [
        ([("slug", ASCENDING)], {"unique": True, "name": "uniq_slug"}),
        (
            [("status", ASCENDING), ("destination_id", ASCENDING)],
            {"name": "status_destination"},
        ),
        ([("is_featured", ASCENDING)], {"name": "featured"}),
    ],
    Collections.CUSTOMERS: [
        (
            [("agent_id", ASCENDING), ("last_name", ASCENDING), ("first_name", ASCENDING)],
            {"name": "agent_name"},
        ),
        ([("agent_id", ASCENDING), ("email", ASCENDING)], {"name": "agent_email"}),
    ],
    Collections.BOOKINGS: [
        ([("reference_code", ASCENDING)], {"unique": True, "name": "uniq_reference_code"}),
        (
            [("agent_id", ASCENDING), ("created_at", DESCENDING)],
            {"name": "agent_created_desc"},
        ),
        ([("status", ASCENDING)], {"name": "status"}),
        ([("package_id", ASCENDING)], {"name": "package"}),
    ],
    Collections.TRANSACTIONS: [
        (
            [("agent_id", ASCENDING), ("created_at", DESCENDING)],
            {"name": "agent_created_desc"},
        ),
        (
            [("agent_id", ASCENDING), ("account_kind", ASCENDING), ("created_at", DESCENDING)],
            {"name": "agent_account_created"},
        ),
        ([("ref_type", ASCENDING), ("ref_id", ASCENDING)], {"name": "ref"}),
        (
            [("idempotency_key", ASCENDING)],
            {
                "unique": True,
                "name": "uniq_idempotency_key",
                "partialFilterExpression": {"idempotency_key": {"$type": "string"}},
            },
        ),
    ],
    Collections.FUND_REQUESTS: [
        ([("agent_id", ASCENDING), ("created_at", DESCENDING)], {"name": "agent_created_desc"}),
        ([("status", ASCENDING), ("created_at", DESCENDING)], {"name": "status_created"}),
    ],
    Collections.COMMISSIONS: [
        ([("agent_id", ASCENDING), ("status", ASCENDING)], {"name": "agent_status"}),
        ([("booking_id", ASCENDING)], {"name": "booking"}),
        ([("withdrawal_id", ASCENDING)], {"name": "withdrawal"}),
    ],
    Collections.COMMISSION_WITHDRAWALS: [
        ([("agent_id", ASCENDING), ("created_at", DESCENDING)], {"name": "agent_created_desc"}),
        ([("status", ASCENDING), ("created_at", DESCENDING)], {"name": "status_created"}),
    ],
    Collections.NOTIFICATIONS: [
        (
            [("user_id", ASCENDING), ("is_read", ASCENDING), ("created_at", DESCENDING)],
            {"name": "user_unread"},
        ),
        (
            [("ref_id", ASCENDING), ("kind", ASCENDING)],
            {
                "unique": True, "name": "uniq_payment_due_alert",
                "partialFilterExpression": {"kind": "booking.payment_due"},
            },
        ),
    ],
    Collections.AUDIT_LOGS: [
        (
            [("target_type", ASCENDING), ("target_id", ASCENDING), ("created_at", DESCENDING)],
            {"name": "target"},
        ),
        ([("actor_user_id", ASCENDING), ("created_at", DESCENDING)], {"name": "actor"}),
        ([("action", ASCENDING), ("created_at", DESCENDING)], {"name": "action"}),
    ],
    Collections.SETTINGS: [
        ([("key", ASCENDING)], {"unique": True, "name": "uniq_key"}),
    ],
    Collections.CONTACT_MESSAGES: [
        ([("status", ASCENDING), ("created_at", DESCENDING)], {"name": "status_created"}),
        ([("email", ASCENDING)], {"name": "email"}),
    ],
    # --- auth collections (Phase 2) ---
    "auth_tokens": [
        ([("token_hash", ASCENDING)], {"unique": True, "name": "uniq_token_hash"}),
        ([("user_id", ASCENDING), ("kind", ASCENDING)], {"name": "user_kind"}),
        ([("expires_at", ASCENDING)], {"name": "ttl_expires_at", "expireAfterSeconds": 0}),
    ],
    Collections.AGENT_PACKAGE_MARKUPS: [
        (
            [("agent_id", ASCENDING), ("package_id", ASCENDING)],
            {"unique": True, "name": "uniq_agent_package"},
        ),
    ],
    Collections.BOOKING_PAYMENTS: [
        ([("booking_id", ASCENDING), ("paid_on", ASCENDING)], {"name": "booking_paid_on"}),
        ([("agent_id", ASCENDING)], {"name": "agent"}),
    ],
    "login_attempts": [
        ([("updated_at", ASCENDING)], {"name": "updated_at"}),
    ],
}


# Default settings rows we ensure exist.
DEFAULT_SETTINGS = [
    {
        "key": "commission_withdrawals_enabled",
        "value": False,
        "description": "Master switch for the agent commission withdrawal flow.",
    },
    {
        "key": "minimum_topup_amount",
        "value": "100.00",
        "description": "Minimum PHP amount per fund request (parsed as Decimal).",
    },
    {
        "key": "maximum_topup_amount",
        "value": "1000000.00",
        "description": "Maximum PHP amount per fund request (parsed as Decimal).",
    },
    {
        "key": "minimum_markup_amount",
        "value": "0.00",
        "description": "Lowest per-pax markup an agent may set on a package.",
    },
    {
        "key": "maximum_markup_amount",
        "value": "10000.00",
        "description": "Highest per-pax markup an agent may set on a package.",
    },
    {
        "key": "brand",
        "value": {
            "name": "Biyahe'Ta Bai Travel",
            "tagline": "Go. Explore. Discover.",
            "currency": "PHP",
            "support_email": "hello@biyahetabaitravel.com",
            "support_phone": "",
        },
        "description": "Public brand metadata used by the marketing site.",
    },
]


async def ensure_collections() -> list[str]:
    db = get_db()
    existing = set(await db.list_collection_names())
    created: list[str] = []
    for name in Collections.all():
        if name not in existing:
            await db.create_collection(name)
            created.append(name)
    return created


async def ensure_indexes() -> dict[str, list[str]]:
    db = get_db()
    result: dict[str, list[str]] = {}
    for collection, specs in INDEXES.items():
        models = [IndexModel(keys, **kwargs) for keys, kwargs in specs]
        names = await db[collection].create_indexes(models)
        result[collection] = names
    return result


async def ensure_default_settings() -> list[str]:
    db = get_db()
    inserted: list[str] = []
    for setting in DEFAULT_SETTINGS:
        existing = await db[Collections.SETTINGS].find_one({"key": setting["key"]})
        if existing:
            continue
        import uuid as _uuid
        doc = {
            "_id": str(_uuid.uuid4()),
            "id": None,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            **setting,
        }
        doc["id"] = doc["_id"]
        await db[Collections.SETTINGS].insert_one(doc)
        inserted.append(setting["key"])
    return inserted


async def init_db() -> dict[str, Any]:
    """Run every idempotent bootstrap step. Returns a summary dict."""
    created = await ensure_collections()
    indexes = await ensure_indexes()
    settings = await ensure_default_settings()
    summary = {
        "collections_created": created,
        "indexes_ensured": {c: len(names) for c, names in indexes.items()},
        "default_settings_inserted": settings,
    }
    logger.info("init_db complete: %s", summary)
    return summary
