"""Hardening tests: balance races + login lockout bypass.

Covers:
- Concurrent admin balance adjustments are never lost ($inc, not read-modify-$set)
- Concurrent debits can't overdraw
- N concurrent approvals of one fund request credit exactly once
- Racing approve vs reject: exactly one wins, no stray credit/notification
- Login lockout can't be dodged by rotating a spoofed X-Forwarded-For
"""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "yongmichael992@gmail.com"
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "Admin@12345")

N = 8


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def admin_cookies(admin):
    # Each thread gets its own Session (requests.Session isn't thread-safe).
    return admin.cookies.get_dict()


@pytest.fixture(scope="module")
def demo_agent_id(admin):
    """A fresh agent owned by this module, so balance before/after checks
    aren't disturbed by other suites (xdist runs modules in parallel)."""
    r = admin.post(f"{API}/admin/agents", json={
        "email": f"race-{uuid.uuid4().hex[:10]}@example.com",
        "display_name": "Race Test Agent",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["agent"]["id"]


def _balance(admin, agent_id) -> Decimal:
    j = admin.get(f"{API}/admin/agents/{agent_id}", timeout=15).json()
    row = j.get("agent") or j
    bal = row.get("booking_balance")
    if bal is None:
        bal = (row.get("booking_account") or {}).get("balance")
    return Decimal(str(bal))


def _parallel(cookies, calls):
    """Run [(method, url, json)] concurrently, each in a fresh session."""
    def run(call):
        method, url, body = call
        s = requests.Session()
        s.cookies.update(cookies)
        return s.request(method, url, json=body, timeout=30)

    with ThreadPoolExecutor(max_workers=len(calls)) as ex:
        return list(ex.map(run, calls))


def _create_pending(admin, agent_id, amount) -> str:
    r = admin.post(f"{API}/admin/fund-requests", json={
        "agent_id": agent_id, "amount": amount,
        "reference_no": f"RACE-{uuid.uuid4().hex[:8]}", "note": "pytest race",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["fund_request"]["id"]


class TestBalanceRaces:
    def test_concurrent_credits_not_lost(self, admin, admin_cookies, demo_agent_id):
        before = _balance(admin, demo_agent_id)
        url = f"{API}/admin/agents/{demo_agent_id}/adjust-balance"
        body = {"kind": "credit", "amount": "11.00", "reason": "pytest race credit"}
        rs = _parallel(admin_cookies, [("POST", url, body)] * N)
        assert all(r.status_code == 200 for r in rs), [r.text for r in rs]
        assert _balance(admin, demo_agent_id) == before + Decimal("11.00") * N

    def test_concurrent_mixed_adjustments(self, admin, admin_cookies, demo_agent_id):
        url = f"{API}/admin/agents/{demo_agent_id}/adjust-balance"
        # Seed enough so every debit can succeed.
        admin.post(url, json={"kind": "credit", "amount": "500.00", "reason": "pytest seed"}, timeout=15)
        before = _balance(admin, demo_agent_id)
        calls = [("POST", url, {"kind": "credit", "amount": "7.00", "reason": "pytest race"})] * N
        calls += [("POST", url, {"kind": "debit", "amount": "3.00", "reason": "pytest race"})] * N
        rs = _parallel(admin_cookies, calls)
        assert all(r.status_code == 200 for r in rs), [r.text for r in rs]
        assert _balance(admin, demo_agent_id) == before + Decimal("4.00") * N

    def test_concurrent_debits_cannot_overdraw(self, admin, admin_cookies, demo_agent_id):
        url = f"{API}/admin/agents/{demo_agent_id}/adjust-balance"
        bal = _balance(admin, demo_agent_id)
        if bal <= 0:
            admin.post(url, json={"kind": "credit", "amount": "100.00", "reason": "pytest seed"}, timeout=15)
            bal = _balance(admin, demo_agent_id)
        # Each debit is the whole balance: exactly one may succeed.
        body = {"kind": "debit", "amount": str(bal), "reason": "pytest overdraw race"}
        rs = _parallel(admin_cookies, [("POST", url, body)] * N)
        ok = [r for r in rs if r.status_code == 200]
        assert len(ok) == 1, [(r.status_code, r.text) for r in rs]
        assert all(r.status_code == 400 for r in rs if r.status_code != 200)
        assert _balance(admin, demo_agent_id) == Decimal("0.00")
        # Restore so other suites keep a usable balance.
        admin.post(url, json={"kind": "credit", "amount": str(bal), "reason": "pytest restore"}, timeout=15)


class TestFundRequestRaces:
    def test_concurrent_approvals_credit_once(self, admin, admin_cookies, demo_agent_id):
        before = _balance(admin, demo_agent_id)
        fid = _create_pending(admin, demo_agent_id, "123.00")
        url = f"{API}/admin/fund-requests/{fid}/approve"
        rs = _parallel(admin_cookies, [("POST", url, {"decision_note": "race"})] * N)
        assert all(r.status_code == 200 for r in rs), [(r.status_code, r.text) for r in rs]
        winners = [r.json() for r in rs if not r.json().get("already_approved")]
        assert len(winners) == 1, [r.json() for r in rs]
        assert _balance(admin, demo_agent_id) == before + Decimal("123.00")

        d = admin.get(f"{API}/admin/fund-requests/{fid}", timeout=15).json()
        assert d["fund_request"]["status"] == "approved"
        assert d["fund_request"]["transaction_id"] == winners[0]["transaction_id"]

        # A later retry is still idempotent and returns the same txn.
        r = admin.post(url, json={}, timeout=15)
        assert r.status_code == 200 and r.json()["already_approved"] is True
        assert r.json()["transaction_id"] == winners[0]["transaction_id"]

    def test_approve_vs_reject_one_wins(self, admin, admin_cookies, demo_agent_id):
        before = _balance(admin, demo_agent_id)
        fid = _create_pending(admin, demo_agent_id, "150.00")
        calls = []
        for _ in range(N // 2):
            calls.append(("POST", f"{API}/admin/fund-requests/{fid}/approve", {}))
            calls.append(("POST", f"{API}/admin/fund-requests/{fid}/reject", {"decision_note": "race reject"}))
        rs = _parallel(admin_cookies, calls)
        assert all(r.status_code in (200, 409) for r in rs), [(r.status_code, r.text) for r in rs]

        status = admin.get(f"{API}/admin/fund-requests/{fid}", timeout=15).json()["fund_request"]["status"]
        rejects_ok = [r for r, c in zip(rs, calls) if c[1].endswith("/reject") and r.status_code == 200]
        approves_fresh = [r for r, c in zip(rs, calls)
                          if c[1].endswith("/approve") and r.status_code == 200
                          and not r.json().get("already_approved")]
        expected = before + (Decimal("150.00") if status == "approved" else Decimal("0"))
        assert _balance(admin, demo_agent_id) == expected
        if status == "approved":
            assert len(approves_fresh) == 1 and not rejects_ok
        else:
            assert status == "rejected" and len(rejects_ok) == 1 and not approves_fresh


class TestLockoutSpoofing:
    def test_rotating_forwarded_for_still_locks(self):
        # Non-existent account: safe to lock, no real user affected.
        email = f"nobody-{uuid.uuid4().hex[:8]}@example.com"
        codes = []
        for i in range(6):
            # "<spoofed>, <proxy>" mimics a client-forged header that our
            # ingress then appends to; only the proxy-added entry is trusted.
            r = requests.post(
                f"{API}/auth/login",
                json={"email": email, "password": "wrong-password"},
                headers={"X-Forwarded-For": f"203.0.113.{i + 1}, 10.0.0.1"},
                timeout=15,
            )
            codes.append(r.status_code)
        assert codes[:5] == [401] * 5, codes
        assert codes[5] == 429, codes
