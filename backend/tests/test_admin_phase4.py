"""Phase 4 backend tests: Admin Dashboard + Agents (list/detail/patch/adjust/txns/audit).

Uses HTTP against the preview URL. Cleans up any invited agents at the end.
"""
from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://agent-travel-desk-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "yongmichael992@gmail.com"
ADMIN_PASS = "Admin@12345"
DEMO_AGENT_EMAIL = "agent.demo@biyahetabai.example.com"
DEMO_AGENT_PASS = "Agent@12345"


def _uniq_email(prefix="phase4"):
    return f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@example.com"


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
        pytest.skip(f"demo agent login failed: {r.text}")
    return s


@pytest.fixture(scope="session")
def demo_agent_id(admin):
    r = admin.get(f"{API}/admin/agents", params={"q": "agent.demo"}, timeout=15)
    assert r.status_code == 200
    agents = r.json()["agents"]
    assert agents, "demo agent missing"
    return agents[0]["id"]


# -------- RBAC on dashboard --------

class TestDashboardRBAC:
    def test_unauth_401(self):
        r = requests.get(f"{API}/admin/dashboard", timeout=10)
        assert r.status_code == 401

    def test_agent_403(self, agent_sess):
        r = agent_sess.get(f"{API}/admin/dashboard", timeout=10)
        assert r.status_code == 403

    def test_admin_200_shape(self, admin):
        r = admin.get(f"{API}/admin/dashboard", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("agent_counts", "catalog", "workflow", "balances", "recent_audit", "currency"):
            assert k in d
        assert d["currency"] == "PHP"
        ac = d["agent_counts"]
        for k in ("active", "invited", "disabled", "total"):
            assert k in ac and isinstance(ac[k], int)
        assert ac["total"] == ac["active"] + ac["invited"] + ac["disabled"]
        assert "booking_total" in d["balances"] and "commission_total" in d["balances"]
        assert isinstance(d["recent_audit"], list)


# -------- Agents list --------

class TestAgentsList:
    def test_unauth_401(self):
        r = requests.get(f"{API}/admin/agents", timeout=10)
        assert r.status_code == 401

    def test_agent_403(self, agent_sess):
        r = agent_sess.get(f"{API}/admin/agents", timeout=10)
        assert r.status_code == 403

    def test_list_returns_demo(self, admin):
        r = admin.get(f"{API}/admin/agents", timeout=15)
        assert r.status_code == 200
        emails = [a["email"] for a in r.json()["agents"]]
        assert DEMO_AGENT_EMAIL in emails

    def test_search_demo(self, admin):
        r = admin.get(f"{API}/admin/agents", params={"q": "demo"}, timeout=15)
        assert r.status_code == 200
        assert any(a["email"] == DEMO_AGENT_EMAIL for a in r.json()["agents"])

    def test_search_zzzz_empty(self, admin):
        r = admin.get(f"{API}/admin/agents", params={"q": "zzzzz"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_status_filter_active(self, admin):
        r = admin.get(f"{API}/admin/agents", params={"status": "active"}, timeout=15)
        assert r.status_code == 200
        assert all(a["status"] == "active" for a in r.json()["agents"])


# -------- Detail + PATCH --------

class TestAgentDetailPatch:
    def test_detail(self, admin, demo_agent_id):
        r = admin.get(f"{API}/admin/agents/{demo_agent_id}", timeout=15)
        assert r.status_code == 200
        a = r.json()["agent"]
        assert a["email"] == DEMO_AGENT_EMAIL
        assert "booking_balance" in a and "commission_balance" in a

    def test_patch_noop(self, admin, demo_agent_id):
        r = admin.patch(f"{API}/admin/agents/{demo_agent_id}", json={}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("changed") is False

    def test_patch_phone(self, admin, demo_agent_id):
        new_phone = f"+63 900 {uuid.uuid4().hex[:6]}"
        r = admin.patch(f"{API}/admin/agents/{demo_agent_id}", json={"phone": new_phone}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("changed") is True
        r2 = admin.get(f"{API}/admin/agents/{demo_agent_id}", timeout=15)
        assert r2.json()["agent"]["phone"] == new_phone


# -------- Adjust balance --------

class TestAdjustBalance:
    def test_credit_then_verify(self, admin, demo_agent_id):
        # baseline
        r0 = admin.get(f"{API}/admin/agents/{demo_agent_id}", timeout=15).json()["agent"]
        prev = Decimal(r0["booking_balance"])
        r = admin.post(f"{API}/admin/agents/{demo_agent_id}/adjust-balance",
                       json={"kind": "credit", "amount": "1000", "reason": "test credit phase4"},
                       timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert Decimal(d["booking_balance"]) == prev + Decimal("1000")
        # Verify persisted
        r2 = admin.get(f"{API}/admin/agents/{demo_agent_id}", timeout=15).json()["agent"]
        assert Decimal(r2["booking_balance"]) == prev + Decimal("1000")
        # Verify txn row
        rt = admin.get(f"{API}/admin/agents/{demo_agent_id}/transactions", timeout=15).json()
        latest = rt["transactions"][0]
        assert latest["type"] == "ADJUSTMENT_CREDIT"
        assert Decimal(latest["balance_after"]) == prev + Decimal("1000")
        # Audit
        ra = admin.get(f"{API}/admin/agents/{demo_agent_id}/audit-logs", timeout=15).json()
        assert any(l["action"] == "agent.adjust_balance.credit" for l in ra["audit_logs"])

    def test_zero_amount_400(self, admin, demo_agent_id):
        r = admin.post(f"{API}/admin/agents/{demo_agent_id}/adjust-balance",
                       json={"kind": "credit", "amount": "0", "reason": "nope"}, timeout=15)
        assert r.status_code in (400, 422)

    def test_short_reason_400(self, admin, demo_agent_id):
        r = admin.post(f"{API}/admin/agents/{demo_agent_id}/adjust-balance",
                       json={"kind": "credit", "amount": "10", "reason": "ab"}, timeout=15)
        assert r.status_code in (400, 422)

    def test_debit_below_zero_400(self, admin, demo_agent_id):
        r = admin.post(f"{API}/admin/agents/{demo_agent_id}/adjust-balance",
                       json={"kind": "debit", "amount": "99999999", "reason": "overdraft test"},
                       timeout=15)
        assert r.status_code == 400

    def test_agent_cannot_adjust(self, agent_sess, demo_agent_id):
        r = agent_sess.post(f"{API}/admin/agents/{demo_agent_id}/adjust-balance",
                            json={"kind": "credit", "amount": "1", "reason": "hacker"}, timeout=10)
        assert r.status_code == 403


# -------- Reset password issues token --------

class TestResetPasswordToken:
    def test_issue_token(self, admin, demo_agent_id):
        r = admin.post(f"{API}/admin/agents/{demo_agent_id}/reset-password", json={}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("reset_token") and d.get("reset_path", "").startswith("/reset-password?token=")


# -------- Disable/Enable cycle with disposable agent --------

class TestDisableEnableLogin:
    @pytest.fixture(scope="class")
    def disposable(self, admin):
        email = _uniq_email("disable")
        r = admin.post(f"{API}/admin/agents",
                       json={"email": email, "display_name": "Disable Test"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        agent_id = d["agent"]["id"]
        # Set password directly so they can log in
        r2 = admin.post(f"{API}/admin/agents/{agent_id}/reset-password",
                        json={"new_password": "Passw0rd!123"}, timeout=15)
        assert r2.status_code == 200
        # Activate
        r3 = admin.patch(f"{API}/admin/agents/{agent_id}/status", json={"status": "active"}, timeout=15)
        assert r3.status_code == 200
        yield {"id": agent_id, "email": email, "password": "Passw0rd!123"}
        # cleanup: leave disabled to be safe
        admin.patch(f"{API}/admin/agents/{agent_id}/status", json={"status": "disabled"}, timeout=15)

    def test_active_can_login(self, disposable):
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"email": disposable["email"], "password": disposable["password"]}, timeout=15)
        assert r.status_code == 200, r.text

    def test_disable_blocks_login(self, admin, disposable):
        r = admin.patch(f"{API}/admin/agents/{disposable['id']}/status",
                        json={"status": "disabled"}, timeout=15)
        assert r.status_code == 200
        s = requests.Session()
        r2 = s.post(f"{API}/auth/login",
                    json={"email": disposable["email"], "password": disposable["password"]}, timeout=15)
        assert r2.status_code in (401, 403)

    def test_reenable_allows_login(self, admin, disposable):
        r = admin.patch(f"{API}/admin/agents/{disposable['id']}/status",
                        json={"status": "active"}, timeout=15)
        assert r.status_code == 200
        s = requests.Session()
        r2 = s.post(f"{API}/auth/login",
                    json={"email": disposable["email"], "password": disposable["password"]}, timeout=15)
        assert r2.status_code == 200


# -------- Public site smoke --------

class TestPublicSmoke:
    def test_home_still_up(self):
        r = requests.get(f"{API}/public/destinations", timeout=15)
        assert r.status_code == 200
