"""File storage for agent logos.

New uploads are stored in MongoDB (``stored_files`` collection) so the app
works on any host — locally, on Atlas, or on Emergent — with no extra
service or credentials. Logos are capped at 2 MB, well under MongoDB's
16 MB document limit.

Paths returned by ``put_object`` look like ``db:<id>``. Any other path is a
legacy Emergent object-storage path (logos uploaded before this change);
those are still read from Emergent when ``EMERGENT_LLM_KEY`` is set, so
existing logos keep working and are never deleted.

Set ``STORAGE_BACKEND=emergent`` to send new uploads to Emergent instead.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid

import requests
from bson.binary import Binary

from core.db import Collections, get_db
from models.base import utc_now_iso

logger = logging.getLogger(__name__)

DB_PREFIX = "db:"


def _backend() -> str:
    return (os.environ.get("STORAGE_BACKEND") or "mongo").strip().lower()


def _legacy_enabled() -> bool:
    return bool((os.environ.get("EMERGENT_LLM_KEY") or "").strip())


# --- MongoDB backend ------------------------------------------------------

async def _db_put(path: str, data: bytes, content_type: str) -> str:
    file_id = str(uuid.uuid4())
    await get_db()[Collections.STORED_FILES].insert_one({
        "_id": file_id,
        "name": path,
        "content_type": content_type,
        "size": len(data),
        "data": Binary(data),
        "created_at": utc_now_iso(),
    })
    return f"{DB_PREFIX}{file_id}"


async def _db_get(path: str) -> bytes:
    doc = await get_db()[Collections.STORED_FILES].find_one({"_id": path[len(DB_PREFIX):]}, {"data": 1})
    if not doc:
        raise FileNotFoundError(path)
    return bytes(doc["data"])


# --- Legacy Emergent object storage ---------------------------------------

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


# --- Public API -----------------------------------------------------------

async def put_object(path: str, data: bytes, content_type: str) -> str:
    if _backend() == "emergent":
        return await asyncio.to_thread(_put, f"{os.environ['APP_STORAGE_PREFIX']}/{path}", data, content_type)
    return await _db_put(path, data, content_type)


async def get_object(path: str) -> bytes:
    if path.startswith(DB_PREFIX):
        return await _db_get(path)
    if not _legacy_enabled():
        raise RuntimeError("Logo is in Emergent storage, but EMERGENT_LLM_KEY is not set")
    return await asyncio.to_thread(_get, path)


def init_storage() -> None:
    logger.info("File storage: new uploads -> %s", _backend())
    if not _legacy_enabled():
        if _backend() == "emergent":
            logger.error("STORAGE_BACKEND=emergent but EMERGENT_LLM_KEY is not set; uploads will fail")
        else:
            logger.info("Emergent storage key not set; legacy (pre-migration) logos can't be loaded here")
        return
    try:
        _init()
        logger.info("Emergent object storage initialised (legacy logos readable)")
    except Exception:
        logger.exception("Emergent object storage init failed")
