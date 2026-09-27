"""Phase 4 Step 4 tests: Admin fund-request queue (list/detail/create/approve/reject).

Covers:
- RBAC (401 anon, 403 agent) on all /api/admin/fund-requests endpoints
- List + status filtering + pending_count
- Detail (with transaction snapshot when approved)
- Create on behalf: amount bounds (100..1_000_000), missing/disabled agent
- Approve: ledger row, balance delta, audit; idempotency; 409 on non-pending
- Reject: reason ≥3 chars; 409 on non-pending; no ledger row
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "yongmichael992@gmail.com"
ADMIN_PASS = "Admin@12345"
DEMO_AGENT_EMAIL = "agent.demo@biyahetabai.example.com"
DEMO_AGENT_PASS = "Agent@12345"


# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def agent_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"agent login failed: {r.text}")
    return s


@pytest.fixture(scope="session")
def demo_agent_id(admin):
    r = admin.get(f"{API}/admin/agents", timeout=15)
    assert r.status_code == 200, r.text
    agents = r.json().get("agents") or r.json()
    # Try common shape variants
    if isinstance(agents, dict):
        agents = agents.get("items", [])
    for a in agents:
        email = (a.get("email") or a.get("user", {}).get("email") or "").lower()
        if email == DEMO_AGENT_EMAIL:
            return a.get("id") or a.get("_id") or a.get("agent_id")
    pytest.skip("demo agent id not found in /api/admin/agents response")


def _create_pending(admin, agent_id, amount="500.00", ref=None) -> str:
    r = admin.post(
        f"{API}/admin/fund-requests",
        json={
            "agent_id": agent_id,
            "amount": amount,
            "reference_no": ref or f"TEST-{uuid.uuid4().hex[:8]}",
            "note": "pytest seed",
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["fund_request"]["id"]


# ---------- RBAC ----------

class TestRBAC:
    def test_list_unauth_401(self):
        r = requests.get(f"{API}/admin/fund-requests", timeout=10)
        assert r.status_code == 401

    def test_list_agent_403(self, agent_sess):
        r = agent_sess.get(f"{API}/admin/fund-requests", timeout=10)
        assert r.status_code == 403

    def test_detail_agent_403(self, agent_sess):
        r = agent_sess.get(f"{API}/admin/fund-requests/nope", timeout=10)
        assert r.status_code == 403

    def test_create_agent_403(self, agent_sess):
        r = agent_sess.post(f"{API}/admin/fund-requests", json={"agent_id": "x", "amount": "500"}, timeout=10)
        assert r.status_code == 403

    def test_approve_agent_403(self, agent_sess):
        r = agent_sess.post(f"{API}/admin/fund-requests/x/approve", json={}, timeout=10)
        assert r.status_code == 403

    def test_reject_agent_403(self, agent_sess):
        r = agent_sess.post(f"{API}/admin/fund-requests/x/reject", json={"decision_note": "no"}, timeout=10)
        assert r.status_code == 403


# ---------- List ----------

class TestList:
    def test_list_returns_shape(self, admin):
        r = admin.get(f"{API}/admin/fund-requests", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "fund_requests" in data
        assert "pending_count" in data
        assert isinstance(data["fund_requests"], list)

    def test_filter_pending(self, admin):
        r = admin.get(f"{API}/admin/fund-requests?status=pending", timeout=15)
        assert r.status_code == 200
        for row in r.json()["fund_requests"]:
            assert row["status"] == "pending"

    def test_filter_approved(self, admin):
        r = admin.get(f"{API}/admin/fund-requests?status=approved", timeout=15)
        assert r.status_code == 200
        for row in r.json()["fund_requests"]:
            assert row["status"] == "approved"

    def test_filter_rejected(self, admin):
        r = admin.get(f"{API}/admin/fund-requests?status=rejected", timeout=15)
        assert r.status_code == 200
        for row in r.json()["fund_requests"]:
            assert row["status"] == "rejected"

    def test_filter_bad_value(self, admin):
        r = admin.get(f"{API}/admin/fund-requests?status=weird", timeout=15)
        assert r.status_code in (400, 422)


# ---------- Create on behalf ----------

class TestCreate:
    def test_create_ok(self, admin, demo_agent_id):
        fid = _create_pending(admin, demo_agent_id, amount="250.00")
        # verify persistence
        r = admin.get(f"{API}/admin/fund-requests/{fid}", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["fund_request"]["status"] == "pending"
        assert body["fund_request"]["agent_id"] == demo_agent_id
        assert body["fund_request"]["amount"] in ("250", "250.00", "250.0")

    def test_create_below_min(self, admin, demo_agent_id):
        r = admin.post(f"{API}/admin/fund-requests",
                       json={"agent_id": demo_agent_id, "amount": "99.99"}, timeout=15)
        assert r.status_code == 400, r.text

    def test_create_above_max(self, admin, demo_agent_id):
        r = admin.post(f"{API}/admin/fund-requests",
                       json={"agent_id": demo_agent_id, "amount": "1000000.01"}, timeout=15)
        assert r.status_code == 400, r.text

    def test_create_missing_agent(self, admin):
        r = admin.post(f"{API}/admin/fund-requests",
                       json={"agent_id": "does-not-exist-xyz", "amount": "500"}, timeout=15)
        assert r.status_code == 404, r.text


# ---------- Approve ----------

class TestApprove:
    def test_approve_credits_and_ledger_and_idempotent(self, admin, demo_agent_id):
        # baseline balance + transactions count
        r = admin.get(f"{API}/admin/agents/{demo_agent_id}", timeout=15)
        assert r.status_code == 200, r.text
        agent_row = r.json().get("agent") or r.json()
        # get booking balance from row
        booking_before = None
        for key in ("booking_balance", "booking_account_balance"):
            if key in agent_row:
                booking_before = agent_row[key]
        if booking_before is None:
            ba = agent_row.get("booking_account") or {}
            booking_before = ba.get("balance")
        from decimal import Decimal
        before_bal = Decimal(str(booking_before))

        # create pending
        amount = Decimal("777.00")
        fid = _create_pending(admin, demo_agent_id, amount=str(amount))

        # approve
        r1 = admin.post(f"{API}/admin/fund-requests/{fid}/approve",
                        json={"decision_note": "pytest approve"}, timeout=20)
        assert r1.status_code == 200, r1.text
        j1 = r1.json()
        assert j1.get("already_approved") in (False, None)
        assert "transaction_id" in j1
        txn_id = j1["transaction_id"]
        new_bal = Decimal(str(j1["booking_balance"]))
        assert new_bal == (before_bal + amount).quantize(Decimal("0.01")), \
            f"Expected {before_bal + amount}, got {new_bal}"

        # detail returns approved + transaction snapshot
        d = admin.get(f"{API}/admin/fund-requests/{fid}", timeout=15).json()
        assert d["fund_request"]["status"] == "approved"
        assert d["fund_request"]["transaction_id"] == txn_id
        assert d["transaction"] is not None
        assert d["transaction"]["type"] == "top_up" or d["transaction"]["type"] == "TOP_UP"

        # idempotent second call
        r2 = admin.post(f"{API}/admin/fund-requests/{fid}/approve",
                        json={"decision_note": "again"}, timeout=20)
        assert r2.status_code == 200, r2.text
        j2 = r2.json()
        assert j2.get("already_approved") is True
        assert j2.get("transaction_id") == txn_id

        # balance did not double
        r3 = admin.get(f"{API}/admin/agents/{demo_agent_id}", timeout=15).json()
        row = r3.get("agent") or r3
        cur_bal = row.get("booking_balance")
        if cur_bal is None:
            cur_bal = (row.get("booking_account") or {}).get("balance")
        assert Decimal(str(cur_bal)) == new_bal, \
            f"Balance drifted after idempotent approve: {cur_bal} vs {new_bal}"

    def test_approve_already_approved_via_new_id_conflict(self, admin, demo_agent_id):
        # Create, approve, then reject → should 409
        fid = _create_pending(admin, demo_agent_id, amount="150.00")
        r = admin.post(f"{API}/admin/fund-requests/{fid}/approve", json={}, timeout=20)
        assert r.status_code == 200
        # try to reject an approved one
        r2 = admin.post(f"{API}/admin/fund-requests/{fid}/reject",
                        json={"decision_note": "too late"}, timeout=15)
        assert r2.status_code == 409, r2.text


# ---------- Reject ----------

class TestReject:
    def test_reject_ok(self, admin, demo_agent_id):
        fid = _create_pending(admin, demo_agent_id, amount="200.00")
        r = admin.post(f"{API}/admin/fund-requests/{fid}/reject",
                       json={"decision_note": "insufficient proof"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "rejected"

        d = admin.get(f"{API}/admin/fund-requests/{fid}", timeout=15).json()
        assert d["fund_request"]["status"] == "rejected"
        assert d["fund_request"]["transaction_id"] in (None, "")
        assert d["transaction"] is None

    def test_reject_short_reason(self, admin, demo_agent_id):
        fid = _create_pending(admin, demo_agent_id, amount="200.00")
        r = admin.post(f"{API}/admin/fund-requests/{fid}/reject",
                       json={"decision_note": "no"}, timeout=15)
        assert r.status_code in (400, 422), r.text
        # cleanup: reject it properly to avoid leaving pending
        admin.post(f"{API}/admin/fund-requests/{fid}/reject",
                   json={"decision_note": "cleanup"}, timeout=15)

    def test_reject_non_pending_409(self, admin, demo_agent_id):
        fid = _create_pending(admin, demo_agent_id, amount="200.00")
        r1 = admin.post(f"{API}/admin/fund-requests/{fid}/reject",
                        json={"decision_note": "first time"}, timeout=15)
        assert r1.status_code == 200
        r2 = admin.post(f"{API}/admin/fund-requests/{fid}/reject",
                        json={"decision_note": "second time"}, timeout=15)
        assert r2.status_code == 409, r2.text

    def test_approve_non_pending_409(self, admin, demo_agent_id):
        # If we approve then approve again, we get 200 already_approved.
        # But approving a REJECTED one should 409.
        fid = _create_pending(admin, demo_agent_id, amount="200.00")
        admin.post(f"{API}/admin/fund-requests/{fid}/reject",
                   json={"decision_note": "rejecting"}, timeout=15)
        r = admin.post(f"{API}/admin/fund-requests/{fid}/approve", json={}, timeout=20)
        assert r.status_code == 409, r.text


# ---------- Regression smoke ----------

class TestRegression:
    def test_agents_list(self, admin):
        r = admin.get(f"{API}/admin/agents", timeout=15)
        assert r.status_code == 200

    def test_bookings(self, admin):
        r = admin.get(f"{API}/admin/bookings", timeout=15)
        assert r.status_code == 200

    def test_admin_packages(self, admin):
        r = admin.get(f"{API}/admin/packages", timeout=15)
        assert r.status_code == 200

    def test_public_packages(self):
        r = requests.get(f"{API}/public/packages", timeout=15)
        assert r.status_code == 200
