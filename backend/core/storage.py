"""Emergent object storage client (used for agent logos)."""
from __future__ import annotations

import asyncio
import logging
import os

import requests

logger = logging.getLogger(__name__)

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"

_storage_key: str | None = None


def _init(force: bool = False) -> str:
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _request(method: str, path: str, headers: dict | None = None, **kw) -> requests.Response:
    for attempt in (0, 1):
        resp = requests.request(method, f"{STORAGE_URL}/objects/{path}",
                                headers={"X-Storage-Key": _init(force=attempt == 1), **(headers or {})}, **kw)
        if resp.status_code != 404:
            break
    resp.raise_for_status()
    return resp


def _put(path: str, data: bytes, content_type: str) -> str:
    return _request("PUT", path, data=data, headers={"Content-Type": content_type}, timeout=120).json()["path"]


def _get(path: str) -> bytes:
    return _request("GET", path, timeout=60).content


async def put_object(path: str, data: bytes, content_type: str) -> str:
    return await asyncio.to_thread(_put, f"{os.environ['APP_STORAGE_PREFIX']}/{path}", data, content_type)


async def get_object(path: str) -> bytes:
    return await asyncio.to_thread(_get, path)


def init_storage() -> None:
    try:
        _init()
        logger.info("Object storage initialised")
    except Exception:
        logger.exception("Object storage init failed")
