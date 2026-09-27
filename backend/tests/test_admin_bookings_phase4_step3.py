"""Phase 4 Step 3 backend tests: Admin Bookings Management.

Covers: RBAC, list + filter + search, detail, state machine validation,
guest-payment-status update (no ledger), and destructive cancel-with-refund
including COMMISSION_REVERSAL. This test intentionally cancels the seed
booking BTB-DEMO-0001 — main agent has reset it to confirmed/paid before
this run.
"""
from __future__ import annotations

import os
from decimal import Decimal

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "yongmichael992@gmail.com"
ADMIN_PASS = "Admin@12345"
AGENT_EMAIL = "agent.demo@biyahetabai.example.com"
AGENT_PASS = "Agent@12345"

DEMO_REF = "BTB-DEMO-0001"


@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def agent():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": AGENT_EMAIL, "password": AGENT_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"agent login failed: {r.text}")
    return s


@pytest.fixture(scope="session")
def demo_booking(admin):
    r = admin.get(f"{API}/admin/bookings", params={"q": "BTB-DEMO"}, timeout=15)
    assert r.status_code == 200, r.text
    bookings = r.json()["bookings"]
    assert bookings, "seed booking missing"
    b = next((x for x in bookings if x["reference_code"] == DEMO_REF), bookings[0])
    return b


# ---- RBAC ----

class TestRBAC:
    def test_list_unauth_401(self):
        r = requests.get(f"{API}/admin/bookings", timeout=10)
        assert r.status_code == 401

    def test_list_agent_403(self, agent):
        r = agent.get(f"{API}/admin/bookings", timeout=10)
        assert r.status_code == 403

    def test_detail_agent_403(self, agent, demo_booking):
        r = agent.get(f"{API}/admin/bookings/{demo_booking['id']}", timeout=10)
        assert r.status_code == 403

    def test_patch_agent_403(self, agent, demo_booking):
        r = agent.patch(f"{API}/admin/bookings/{demo_booking['id']}/status",
                        json={"status": "completed"}, timeout=10)
        assert r.status_code == 403


# ---- List / filter / search ----

class TestListing:
    def test_list_contains_demo(self, admin):
        r = admin.get(f"{API}/admin/bookings", timeout=15)
        assert r.status_code == 200
        refs = [b["reference_code"] for b in r.json()["bookings"]]
        assert DEMO_REF in refs

    def test_summary_shape(self, admin, demo_booking):
        assert demo_booking["agent"] and demo_booking["agent"]["display_name"]
        assert demo_booking["package"] and demo_booking["package"]["slug"]
        assert demo_booking["customer"] and demo_booking["customer"]["name"]
        assert demo_booking["currency"] == "PHP"
        assert demo_booking["status"] == "confirmed"
        assert demo_booking["guest_payment_status"] == "paid"

    def test_status_filter_confirmed(self, admin):
        r = admin.get(f"{API}/admin/bookings", params={"status": "confirmed"}, timeout=15)
        assert r.status_code == 200
        assert all(b["status"] == "confirmed" for b in r.json()["bookings"])

    def test_status_filter_pending_empty(self, admin):
        r = admin.get(f"{API}/admin/bookings", params={"status": "pending"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_search_hit(self, admin):
        r = admin.get(f"{API}/admin/bookings", params={"q": "BTB-DEMO"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_search_miss(self, admin):
        r = admin.get(f"{API}/admin/bookings", params={"q": "zzzzzz"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["total"] == 0


# ---- Detail ----

class TestDetail:
    def test_detail(self, admin, demo_booking):
        r = admin.get(f"{API}/admin/bookings/{demo_booking['id']}", timeout=15)
        assert r.status_code == 200
        d = r.json()["booking"]
        assert d["reference_code"] == DEMO_REF
        assert d["agent"]["email"]
        assert d["package"]["slug"]
        assert isinstance(d["status_history"], list) and len(d["status_history"]) >= 2

    def test_detail_txns_has_debit_and_accrual(self, admin, demo_booking):
        r = admin.get(f"{API}/admin/bookings/{demo_booking['id']}/transactions", timeout=15)
        assert r.status_code == 200
        types = [t["type"] for t in r.json()["transactions"]]
        assert "BOOKING_DEBIT" in types
        assert "COMMISSION_ACCRUAL" in types

    def test_detail_404(self, admin):
        r = admin.get(f"{API}/admin/bookings/does-not-exist", timeout=10)
        assert r.status_code == 404


# ---- State machine invalid transitions ----

class TestInvalidTransitions:
    def test_confirmed_to_pending_400(self, admin, demo_booking):
        r = admin.patch(f"{API}/admin/bookings/{demo_booking['id']}/status",
                        json={"status": "pending"}, timeout=15)
        assert r.status_code == 400
        assert "cannot" in r.text.lower() or "confirmed" in r.text.lower()


# ---- Guest payment status (informational only) ----

class TestGuestPaymentStatus:
    def test_toggle_partial_no_ledger_row(self, admin, demo_booking):
        bid = demo_booking["id"]
        # baseline txn count
        before = len(admin.get(f"{API}/admin/bookings/{bid}/transactions", timeout=15).json()["transactions"])
        r = admin.patch(f"{API}/admin/bookings/{bid}/guest-payment-status",
                        json={"status": "partial", "note": "Testing partial"}, timeout=15)
        assert r.status_code == 200
        d = admin.get(f"{API}/admin/bookings/{bid}", timeout=15).json()["booking"]
        assert d["guest_payment_status"] == "partial"
        after = len(admin.get(f"{API}/admin/bookings/{bid}/transactions", timeout=15).json()["transactions"])
        assert after == before, "guest-payment-status must NOT create a ledger row"
        # restore to paid so UI test still sees 'paid' visually — cancel is next
        r2 = admin.patch(f"{API}/admin/bookings/{bid}/guest-payment-status",
                         json={"status": "paid"}, timeout=15)
        assert r2.status_code == 200


# ---- Destructive: Cancel-with-refund + commission reversal ----

class TestCancelWithRefund:
    """Must run after TestGuestPaymentStatus. Marks the booking terminal."""

    def test_cancel_with_refund(self, admin, demo_booking):
        bid = demo_booking["id"]
        # snapshot agent balances before
        agent_id = demo_booking["agent"]["id"]
        pre_agent = admin.get(f"{API}/admin/agents/{agent_id}", timeout=15).json()["agent"]
        pre_booking_bal = Decimal(pre_agent["booking_balance"])
        pre_commission_bal = Decimal(pre_agent["commission_balance"])
        total_cost = Decimal(demo_booking["total_agent_cost"])
        total_commission = Decimal(demo_booking["total_commission_amount"])
        assert total_cost > 0
        assert total_commission > 0

        r = admin.patch(f"{API}/admin/bookings/{bid}/status",
                        json={"status": "cancelled", "refund": True,
                              "reason": "Automated phase4-step3 cancel test"}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "cancelled"
        assert body.get("refund_transaction_id")
        assert body.get("commission_reversal_transaction_id")

        # Booking now cancelled
        d = admin.get(f"{API}/admin/bookings/{bid}", timeout=15).json()["booking"]
        assert d["status"] == "cancelled"
        assert len(d["status_history"]) >= 3

        # Ledger has BOOKING_REFUND(+cost) and COMMISSION_REVERSAL(-commission)
        txns = admin.get(f"{API}/admin/bookings/{bid}/transactions", timeout=15).json()["transactions"]
        refund = next((t for t in txns if t["type"] == "BOOKING_REFUND"), None)
        reversal = next((t for t in txns if t["type"] == "COMMISSION_REVERSAL"), None)
        assert refund and Decimal(refund["amount"]) == total_cost
        assert reversal and Decimal(reversal["amount"]) == -total_commission

        # Agent balance moved
        post_agent = admin.get(f"{API}/admin/agents/{agent_id}", timeout=15).json()["agent"]
        assert Decimal(post_agent["booking_balance"]) == pre_booking_bal + total_cost
        assert Decimal(post_agent["commission_balance"]) == pre_commission_bal - total_commission

    def test_terminal_cancelled_cannot_complete(self, admin, demo_booking):
        r = admin.patch(f"{API}/admin/bookings/{demo_booking['id']}/status",
                        json={"status": "completed"}, timeout=15)
        assert r.status_code == 400

    def test_terminal_cancelled_cannot_reopen(self, admin, demo_booking):
        r = admin.patch(f"{API}/admin/bookings/{demo_booking['id']}/status",
                        json={"status": "confirmed"}, timeout=15)
        assert r.status_code == 400


# ---- Regression: existing endpoints still work ----

class TestRegression:
    def test_dashboard(self, admin):
        r = admin.get(f"{API}/admin/dashboard", timeout=15)
        assert r.status_code == 200

    def test_agents_list(self, admin):
        r = admin.get(f"{API}/admin/agents", timeout=15)
        assert r.status_code == 200

    def test_public_destinations(self):
        r = requests.get(f"{API}/public/destinations", timeout=15)
        assert r.status_code == 200

    def test_public_packages(self):
        r = requests.get(f"{API}/public/packages", timeout=15)
        assert r.status_code == 200
