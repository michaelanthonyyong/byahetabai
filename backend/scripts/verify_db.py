"""Database verification report.

Runs a battery of read-only checks against the current database and prints
a summary.  Non-zero exit code on any failure so it can be wired into CI
later.  Safe to run multiple times.

Usage:
    python -m backend.scripts.verify_db
"""
from __future__ import annotations

import asyncio
import json
import os
import logging
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

# Support running as a script from /app.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db import Collections, get_db  # noqa: E402
from core.init_db import INDEXES, init_db  # noqa: E402
from models.base import money_from_bson  # noqa: E402

logger = logging.getLogger(__name__)


def _ok(label: str) -> dict:
    return {"check": label, "status": "PASS"}


def _fail(label: str, detail: Any) -> dict:
    return {"check": label, "status": "FAIL", "detail": detail}


async def check_collections_exist() -> list[dict]:
    db = get_db()
    existing = set(await db.list_collection_names())
    return [
        _ok(f"collection[{c}]") if c in existing else _fail(f"collection[{c}]", "missing")
        for c in Collections.all()
    ]


async def check_indexes() -> list[dict]:
    db = get_db()
    results = []
    for collection, specs in INDEXES.items():
        expected = {kwargs.get("name") for _, kwargs in specs if kwargs.get("name")}
        info = await db[collection].index_information()
        actual = set(info.keys())
        missing = expected - actual
        if missing:
            results.append(_fail(f"indexes[{collection}]", f"missing={sorted(missing)}"))
        else:
            results.append(_ok(f"indexes[{collection}] ({len(expected)} defined)"))
    return results


async def check_unique_email() -> dict:
    """Duplicate insert into ``users.email`` must be rejected."""
    from pymongo.errors import DuplicateKeyError
    db = get_db()
    probe = "verify.unique.email@biyahetabai.example.com"
    await db[Collections.USERS].delete_many({"email": probe})
    doc = {
        "_id": "verify-1", "id": "verify-1",
        "email": probe, "password_hash": "x",
        "role": "agent", "status": "active", "display_name": "Probe",
        "created_at": "1970-01-01T00:00:00+00:00", "updated_at": "1970-01-01T00:00:00+00:00",
    }
    dup = {**doc, "_id": "verify-2", "id": "verify-2"}
    try:
        await db[Collections.USERS].insert_one(doc)
        try:
            await db[Collections.USERS].insert_one(dup)
            return _fail("constraint[users.email unique]", "duplicate accepted")
        except DuplicateKeyError:
            return _ok("constraint[users.email unique]")
        finally:
            await db[Collections.USERS].delete_many({"email": probe})
    except Exception as e:  # noqa: BLE001
        await db[Collections.USERS].delete_many({"email": probe})
        return _fail("constraint[users.email unique]", str(e))


async def check_seed_relationships() -> list[dict]:
    db = get_db()
    checks: list[dict] = []

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@biyahetabai.example.com").lower().strip()
    admin = await db[Collections.USERS].find_one({"email": admin_email})
    if not admin:
        return [_fail("seed[admin exists]", "not found")]
    checks.append(_ok("seed[admin exists]"))

    agent_user = await db[Collections.USERS].find_one({"email": "agent.demo@biyahetabai.example.com"})
    if not agent_user:
        return checks + [_fail("seed[agent user exists]", "not found")]
    checks.append(_ok("seed[agent user exists]"))

    profile = await db[Collections.AGENT_PROFILES].find_one({"user_id": agent_user["_id"]})
    if not profile:
        return checks + [_fail("seed[agent profile FK]", "no profile links to agent user")]
    checks.append(_ok("seed[agent profile → user FK]"))

    # Packages → Destinations
    pkgs = await db[Collections.PACKAGES].find({}).to_list(length=None)
    dest_ids = {d["_id"] for d in await db[Collections.DESTINATIONS].find({}).to_list(length=None)}
    bad = [p["slug"] for p in pkgs if p["destination_id"] not in dest_ids]
    checks.append(_ok("seed[packages → destinations FK]") if not bad else _fail("seed[packages → destinations FK]", bad))

    # Bookings → agent, customer, package
    for booking in await db[Collections.BOOKINGS].find({}).to_list(length=None):
        if not await db[Collections.AGENT_PROFILES].find_one({"_id": booking["agent_id"]}):
            checks.append(_fail(f"seed[booking {booking['reference_code']} → agent]", "orphan"))
            continue
        if not await db[Collections.CUSTOMERS].find_one({"_id": booking["customer_id"]}):
            checks.append(_fail(f"seed[booking {booking['reference_code']} → customer]", "orphan"))
            continue
        if not await db[Collections.PACKAGES].find_one({"_id": booking["package_id"]}):
            checks.append(_fail(f"seed[booking {booking['reference_code']} → package]", "orphan"))
            continue
        checks.append(_ok(f"seed[booking {booking['reference_code']} FKs]"))

    # Every fund_request with a transaction_id points at a real txn
    for fr in await db[Collections.FUND_REQUESTS].find({}).to_list(length=None):
        if fr.get("transaction_id"):
            if not await db[Collections.TRANSACTIONS].find_one({"_id": fr["transaction_id"]}):
                checks.append(_fail("seed[fund_request → transaction]", fr["_id"]))
                continue
        checks.append(_ok(f"seed[fund_request {fr['_id'][:8]} → transaction]"))

    return checks


async def check_financial_invariants() -> list[dict]:
    """SUM(signed txn.amount, per account) must equal cached agent balance."""
    db = get_db()
    checks: list[dict] = []

    totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    async for txn in db[Collections.TRANSACTIONS].find({}):
        key = (txn["agent_id"], txn["account_kind"])
        totals[key] += money_from_bson(txn["amount"])

    async for agent in db[Collections.AGENT_PROFILES].find({}):
        booking_bal = money_from_bson(agent["booking_account"]["balance"])
        commission_bal = money_from_bson(agent["commission_account"]["balance"])
        exp_booking = totals.get((agent["_id"], "booking"), Decimal("0.00"))
        exp_commission = totals.get((agent["_id"], "commission"), Decimal("0.00"))

        if booking_bal == exp_booking:
            checks.append(_ok(f"invariant[booking balance = SUM(txn) for {agent['display_name']}]"))
        else:
            checks.append(_fail(
                f"invariant[booking balance for {agent['display_name']}]",
                f"cached={booking_bal} vs ledger={exp_booking}",
            ))

        if commission_bal == exp_commission:
            checks.append(_ok(f"invariant[commission balance = SUM(txn) for {agent['display_name']}]"))
        else:
            checks.append(_fail(
                f"invariant[commission balance for {agent['display_name']}]",
                f"cached={commission_bal} vs ledger={exp_commission}",
            ))

    return checks


async def check_fund_request_ledger() -> list[dict]:
    """Approved fund requests ⇔ exactly one TOP_UP of the same amount.

    Catches a crash in the middle of ``approve_fund_request`` (request marked
    approved but never credited, or credited but not linked) and any credit
    for a request that is not approved.
    """
    db = get_db()
    # Match on what the ledger row refers to, not its idempotency-key label
    # (seed.py labels its demo top-up "seed-topup-…").
    txns: dict[str, dict] = {}
    async for t in db[Collections.TRANSACTIONS].find(
        {"type": "TOP_UP", "ref_type": "fund_request"},
    ):
        txns[t["ref_id"]] = t

    problems: list[str] = []
    async for fr in db[Collections.FUND_REQUESTS].find({}):
        t = txns.pop(fr["_id"], None)
        if fr.get("status") == "approved":
            if not t:
                problems.append(f"{fr['_id']}: approved but no TOP_UP transaction")
            elif money_from_bson(t["amount"]) != money_from_bson(fr["amount"]):
                problems.append(f"{fr['_id']}: amount {fr['amount']} vs TOP_UP {t['amount']}")
            elif fr.get("transaction_id") != t["_id"]:
                problems.append(f"{fr['_id']}: transaction_id not linked to {t['_id']}")
        elif t:
            problems.append(f"{fr['_id']}: status {fr.get('status')} but has TOP_UP {t['_id']}")
    problems += [f"{fid}: TOP_UP for a missing fund request" for fid in txns]

    label = "invariant[approved fund requests ⇔ one TOP_UP each]"
    return [_fail(label, problems) if problems else _ok(label)]


async def check_idempotency_key_partial_unique() -> dict:
    """Duplicate ``idempotency_key`` (non-null) must be rejected; nulls allowed."""
    from pymongo.errors import DuplicateKeyError
    db = get_db()
    key = "verify-idem-1"
    await db[Collections.TRANSACTIONS].delete_many({"idempotency_key": key})
    base = {
        "_id": "verify-txn-1", "id": "verify-txn-1",
        "agent_id": "x", "account_kind": "booking",
        "type": "ADJUSTMENT_CREDIT",
        "amount": 0, "balance_after": 0, "currency": "PHP",
        "idempotency_key": key,
        "created_by_user_id": "x",
        "created_at": "1970-01-01T00:00:00+00:00", "updated_at": "1970-01-01T00:00:00+00:00",
    }
    dup = {**base, "_id": "verify-txn-2", "id": "verify-txn-2"}
    try:
        await db[Collections.TRANSACTIONS].insert_one(base)
        try:
            await db[Collections.TRANSACTIONS].insert_one(dup)
            return _fail("constraint[transactions.idempotency_key unique]", "duplicate accepted")
        except DuplicateKeyError:
            return _ok("constraint[transactions.idempotency_key unique]")
        finally:
            await db[Collections.TRANSACTIONS].delete_many({"idempotency_key": key})
    except Exception as e:  # noqa: BLE001
        await db[Collections.TRANSACTIONS].delete_many({"idempotency_key": key})
        return _fail("constraint[transactions.idempotency_key unique]", str(e))


async def summary_counts() -> dict[str, int]:
    db = get_db()
    return {c: await db[c].count_documents({}) for c in Collections.all()}


async def main() -> int:
    print("== Biyahe'Ta Bai Travel — Database Verification Report ==\n")
    print(">> Running idempotent init_db() ...")
    init_summary = await init_db()
    print(json.dumps(init_summary, indent=2))

    print("\n>> Collection existence ...")
    results: list[dict] = []
    results += await check_collections_exist()

    print(">> Indexes ...")
    results += await check_indexes()

    print(">> Unique-email constraint ...")
    results.append(await check_unique_email())

    print(">> Idempotency-key partial unique ...")
    results.append(await check_idempotency_key_partial_unique())

    print(">> Seed relationships (FKs) ...")
    results += await check_seed_relationships()

    print(">> Financial invariants ...")
    results += await check_financial_invariants()
    results += await check_fund_request_ledger()

    print("\n== Results ==")
    passes = [r for r in results if r["status"] == "PASS"]
    fails = [r for r in results if r["status"] == "FAIL"]
    for r in results:
        marker = "OK" if r["status"] == "PASS" else "!!"
        print(f"  [{marker}] {r['check']}" + (f"  — {r.get('detail')}" if r["status"] == "FAIL" else ""))
    print(f"\nPASS: {len(passes)}   FAIL: {len(fails)}")

    counts = await summary_counts()
    print("\n== Collection counts ==")
    for c, n in counts.items():
        print(f"  {c}: {n}")

    return 0 if not fails else 1


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.WARNING)
    sys.exit(asyncio.run(main()))
