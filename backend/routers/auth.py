"""Public auth endpoints under /api/auth."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field

from core import auth_service
from core.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- request / response schemas -----------------------------------------

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class SetPasswordIn(BaseModel):
    token: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    status: str
    display_name: str


def _user_out(user: dict) -> dict:
    return {
        "id": user["_id"],
        "email": user["email"],
        "role": user["role"],
        "status": user.get("status", "active"),
        "display_name": user.get("display_name", user["email"]),
    }


# --- cookie helpers ------------------------------------------------------

_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
_COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax")
_ACCESS_MAX_AGE = int(os.environ.get("JWT_ACCESS_TTL_MIN", "60")) * 60
_REFRESH_MAX_AGE = int(os.environ.get("JWT_REFRESH_TTL_DAYS", "7")) * 86400


def _set_auth_cookies(resp: Response, access: Optional[str], refresh: Optional[str]) -> None:
    if access is not None:
        resp.set_cookie(
            "access_token", access,
            httponly=True, secure=_COOKIE_SECURE, samesite=_COOKIE_SAMESITE,
            max_age=_ACCESS_MAX_AGE, path="/",
        )
    if refresh is not None:
        resp.set_cookie(
            "refresh_token", refresh,
            httponly=True, secure=_COOKIE_SECURE, samesite=_COOKIE_SAMESITE,
            max_age=_REFRESH_MAX_AGE, path="/",
        )


def _clear_auth_cookies(resp: Response) -> None:
    resp.delete_cookie(
        "access_token", path="/",
        secure=_COOKIE_SECURE, samesite=_COOKIE_SAMESITE, httponly=True,
    )
    resp.delete_cookie(
        "refresh_token", path="/",
        secure=_COOKIE_SECURE, samesite=_COOKIE_SAMESITE, httponly=True,
    )


def _client_ip(request: Request) -> Optional[str]:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


# --- endpoints -----------------------------------------------------------

@router.post("/login")
async def login(payload: LoginIn, request: Request, response: Response):
    result = await auth_service.login(payload.email, payload.password, _client_ip(request))
    _set_auth_cookies(response, result["access_token"], result["refresh_token"])
    return {"user": _user_out(result["user"])}


@router.post("/logout")
async def logout(response: Response, _user: dict = Depends(get_current_user)):
    _clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": _user_out(user)}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        _clear_auth_cookies(response)
        return Response(status_code=401)
    access, user = await auth_service.refresh_access_token(token)
    _set_auth_cookies(response, access, None)
    return {"user": _user_out(user)}


@router.post("/accept-invite")
async def accept_invite(payload: SetPasswordIn):
    return await auth_service.accept_invite(payload.token, payload.new_password)


@router.post("/reset-password")
async def reset_password(payload: SetPasswordIn):
    return await auth_service.reset_password_with_token(payload.token, payload.new_password)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordIn, user: dict = Depends(get_current_user)
):
    await auth_service.change_password(user["_id"], payload.current_password, payload.new_password)
    return {"ok": True}
