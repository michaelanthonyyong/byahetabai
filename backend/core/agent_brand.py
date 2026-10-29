"""Agent branding used on customer documents."""
from __future__ import annotations

import logging

from core.storage import get_object

logger = logging.getLogger(__name__)


def brand_name(profile: dict) -> str:
    return profile.get("business_name") or profile.get("agency_name") or profile.get("display_name") or ""


async def agent_brand(profile: dict, email: str | None) -> dict:
    logo = None
    if profile.get("logo_path"):
        try:
            logo = await get_object(profile["logo_path"])
        except Exception:
            logger.exception("Could not load logo for agent %s", profile["_id"])
    lines = [x for x in [profile.get("address"), " · ".join(y for y in [profile.get("phone"), email] if y)] if x]
    return {"name": brand_name(profile), "logo": logo, "lines": lines}
