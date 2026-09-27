"""FastAPI dependencies for authentication + RBAC.

* ``get_current_user`` — decodes the access token from cookie (fallback to
  ``Authorization: Bearer``) and loads the DB user.  Raises 401 on failure.
* ``require_role(*roles)`` — factory returning a dep that adds role gating.
* ``get_current_agent_profile_id`` — for agent-scoped endpoints, resolves
  the caller's agent profile id.  Never accepts an agent id from the client.
"""
from __future__ import annotations

from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status

from .db import Collections, get_db
from .security import decode_token


UNAUTH = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
FORBIDDEN = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _extract_token(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if token:
        return token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def get_current_user(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise UNAUTH
    try:
        payload = decode_token(token, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise UNAUTH

    user_id = payload.get("sub")
    if not user_id:
        raise UNAUTH

    user = await get_db()[Collections.USERS].find_one({"_id": user_id})
    if not user or user.get("status") == "disabled":
        raise UNAUTH

    user.pop("password_hash", None)
    return user


def require_role(*roles: str):
    """Return a FastAPI dependency that also enforces role membership."""

    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise FORBIDDEN
        return user

    return _dep


async def get_current_agent_profile_id(user: dict = Depends(get_current_user)) -> str:
    """Resolve the ``agent_profiles._id`` for the calling agent user.

    Enforces the isolation rule: the id is derived from the JWT, never
    from a request parameter.
    """
    if user.get("role") != "agent":
        raise FORBIDDEN
    profile = await get_db()[Collections.AGENT_PROFILES].find_one({"user_id": user["_id"]})
    if not profile:
        # Should never happen — every agent has a 1:1 profile.
        raise HTTPException(status_code=500, detail="Agent profile missing for user")
    return profile["_id"]
