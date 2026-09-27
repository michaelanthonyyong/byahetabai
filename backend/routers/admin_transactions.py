"""Global financial ledger (read-only) for admins.

* GET /api/admin/transactions — paginated, filterable
* GET /api/admin/transactions/export.csv — full-result CSV download
"""
from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from core.db import Collections, get_db
from core.deps import require_role
from models.base import money_from_bson
from models.transaction import TransactionType

router = APIRouter(prefix="/api/admin/transactions", tags=["admin:transactions"])

require_admin = require_role("admin")

_TYPE_VALUES = "|".join(t.value for t in TransactionType)


def _build_query(
    agent_id: Optional[str],
    account_kind: Optional[str],
    type_: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict:
    q: dict = {}
    if agent_id:
        q["agent_id"] = agent_id
    if account_kind:
        q["account_kind"] = account_kind
    if type_:
        q["type"] = type_
    if date_from or date_to:
        rng: dict = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        q["created_at"] = rng
    return q


async def _resolve_agent_names(rows: list[dict]) -> dict[str, dict]:
    db = get_db()
    ids = list({r["agent_id"] for r in rows})
    return {
        a["_id"]: a
        async for a in db[Collections.AGENT_PROFILES].find(
            {"_id": {"$in": ids}}, {"display_name": 1, "agency_name": 1}
        )
    }


def _row_out(r: dict, agent: Optional[dict]) -> dict:
    return {
        "id": r["_id"],
        "created_at": r.get("created_at"),
        "agent_id": r["agent_id"],
        "agent": (
            {"id": agent["_id"], "display_name": agent.get("display_name"),
             "agency_name": agent.get("agency_name")}
            if agent else None
        ),
        "account_kind": r.get("account_kind"),
        "type": r.get("type"),
        "amount": str(money_from_bson(r["amount"])),
        "balance_after": str(money_from_bson(r["balance_after"])),
        "ref_type": r.get("ref_type"),
        "ref_id": r.get("ref_id"),
        "note": r.get("note"),
    }


@router.get("")
async def list_transactions(
    admin: dict = Depends(require_admin),
    agent_id: Optional[str] = Query(default=None),
    account_kind: Optional[str] = Query(default=None, pattern="^(booking|commission)$"),
    type: Optional[str] = Query(default=None),  # noqa: A002 (fastapi query param name)
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    if type is not None and type not in {t.value for t in TransactionType}:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown type. Allowed: {_TYPE_VALUES}")
    db = get_db()
    q = _build_query(agent_id, account_kind, type, date_from, date_to)
    total = await db[Collections.TRANSACTIONS].count_documents(q)
    rows = await (
        db[Collections.TRANSACTIONS].find(q).sort("created_at", -1)
        .skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    )
    agents = await _resolve_agent_names(rows)
    return {
        "transactions": [_row_out(r, agents.get(r["agent_id"])) for r in rows],
        "page": page, "page_size": page_size, "total": total,
    }


@router.get("/export.csv")
async def export_transactions_csv(
    admin: dict = Depends(require_admin),
    agent_id: Optional[str] = Query(default=None),
    account_kind: Optional[str] = Query(default=None, pattern="^(booking|commission)$"),
    type: Optional[str] = Query(default=None),  # noqa: A002
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=50000),
):
    db = get_db()
    q = _build_query(agent_id, account_kind, type, date_from, date_to)
    rows = await (
        db[Collections.TRANSACTIONS].find(q).sort("created_at", -1)
        .limit(limit).to_list(length=limit)
    )
    agents = await _resolve_agent_names(rows)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "created_at", "agent_id", "agent_display_name", "agency_name",
        "account_kind", "type", "amount", "balance_after",
        "ref_type", "ref_id", "note",
    ])
    for r in rows:
        a = agents.get(r["agent_id"], {})
        writer.writerow([
            r.get("created_at", ""),
            r["agent_id"],
            a.get("display_name", ""),
            a.get("agency_name", ""),
            r.get("account_kind", ""),
            r.get("type", ""),
            str(money_from_bson(r["amount"])),
            str(money_from_bson(r["balance_after"])),
            r.get("ref_type") or "",
            r.get("ref_id") or "",
            (r.get("note") or "").replace("\n", " "),
        ])
    buf.seek(0)
    filename = "transactions.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
