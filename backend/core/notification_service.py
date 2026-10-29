"""In-portal alerts for agents (bell + dashboard list)."""
from __future__ import annotations

import logging
from typing import Optional

from core.db import Collections, get_db
from models.notification import Notification

logger = logging.getLogger(__name__)


async def notify_agent(
    *, agent_id: str, kind: str, title: str, body: str,
    ref_type: Optional[str] = None, ref_id: Optional[str] = None,
) -> None:
    db = get_db()
    try:
        profile = await db[Collections.AGENT_PROFILES].find_one({"_id": agent_id}, {"user_id": 1})
        if not profile:
            return
        await db[Collections.NOTIFICATIONS].insert_one(
            Notification(
                user_id=profile["user_id"], kind=kind, title=title, body=body,
                ref_type=ref_type, ref_id=ref_id,
            ).to_mongo()
        )
    except Exception:
        logger.exception("Failed to write agent notification %s for %s", kind, agent_id)
