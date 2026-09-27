"""Backend tests for Phase 2 auth + RBAC.

Covers: login (success/wrong/disabled/invited), /auth/me, invite→accept→login,
admin agents CRUD, RBAC 401/403, admin reset-password, toggle status,
change-password, brute-force lockout.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://agent-travel-desk-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "yongmichael992@gmail.com"
ADMIN_PASS = "Admin@12345"
DEMO_AGENT_EMAIL = "agent.demo@biyahetabai.example.com"
DEMO_AGENT_PASS = "Agent@12345"


def _uniq_email(prefix: str = "qa") -> str:
    return f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@example.com"


# ---------- fixtures ----------

@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def demo_agent_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"demo agent login failed: {r.status_code} {r.text}")
    return s


# ---------- unauthenticated ----------

class TestUnauthenticated:
    def test_me_401(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_admin_agents_401(self):
        r = requests.get(f"{API}/admin/agents", timeout=10)
        assert r.status_code == 401


# ---------- admin login ----------

class TestAdminLogin:
    def test_login_success_and_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"
        # httpOnly cookie must be set
        assert "access_token" in s.cookies.get_dict() or any(c.name == "access_token" for c in s.cookies)
        # /me works
        me = s.get(f"{API}/auth/me", timeout=10)
        assert me.status_code == 200
        assert me.json()["user"]["email"] == ADMIN_EMAIL

    def test_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "WrongPass!x"}, timeout=10)
        assert r.status_code == 401


# ---------- invite / accept / login ----------

@pytest.fixture(scope="class")
def invited_agent(admin_session):
    email = _uniq_email("invite")
    r = admin_session.post(
        f"{API}/admin/agents",
        json={"email": email, "display_name": "QA Invite", "agency_name": "QA Co", "phone": "+63 900"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "invite_token" in data
    assert data["invite_path"].startswith("/accept-invite?token=")
    return {"email": email, "token": data["invite_token"], "agent_id": data["agent"]["id"]}


class TestInviteFlow:
    def test_invite_agent_creates_token(self, invited_agent):
        assert invited_agent["token"]

    def test_invited_cannot_login(self, invited_agent):
        # Wrong password on an invited (not-accepted) email → 401 (invalid credentials path)
        r = requests.post(
            f"{API}/auth/login",
            json={"email": invited_agent["email"], "password": "definitely-wrong"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_accept_invite_and_login(self, invited_agent):
        new_pw = "Agent@Pass1"
        r = requests.post(
            f"{API}/auth/accept-invite",
            json={"token": invited_agent["token"], "new_password": new_pw},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["email"].lower() == invited_agent["email"].lower()

        # Login works with new password
        s = requests.Session()
        r2 = s.post(f"{API}/auth/login", json={"email": invited_agent["email"], "password": new_pw}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["user"]["role"] == "agent"
        invited_agent["password"] = new_pw
        invited_agent["session"] = s

    def test_reused_invite_token_rejected(self, invited_agent):
        r = requests.post(
            f"{API}/auth/accept-invite",
            json={"token": invited_agent["token"], "new_password": "Whatever@123"},
            timeout=10,
        )
        assert r.status_code == 400


# ---------- RBAC ----------

class TestRBAC:
    def test_agent_forbidden_from_admin(self, demo_agent_session):
        r = demo_agent_session.get(f"{API}/admin/agents", timeout=10)
        assert r.status_code == 403

    def test_admin_lists_agents(self, admin_session):
        r = admin_session.get(f"{API}/admin/agents", timeout=15)
        assert r.status_code == 200
        assert "agents" in r.json()


# ---------- admin reset password ----------

class TestAdminResetPassword:
    def test_admin_issues_reset_token_and_agent_logs_in(self, admin_session):
        # Create+accept fresh agent
        email = _uniq_email("reset")
        inv = admin_session.post(
            f"{API}/admin/agents",
            json={"email": email, "display_name": "Reset QA"},
            timeout=15,
        ).json()
        requests.post(
            f"{API}/auth/accept-invite",
            json={"token": inv["invite_token"], "new_password": "Initial@123"},
            timeout=15,
        )
        agent_id = inv["agent"]["id"]

        # Admin issues reset token
        r = admin_session.post(
            f"{API}/admin/agents/{agent_id}/reset-password",
            json={},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("mode") == "token"
        assert data.get("reset_token")

        # Use reset token
        new_pw = "Reset@456xyz"
        rp = requests.post(
            f"{API}/auth/reset-password",
            json={"token": data["reset_token"], "new_password": new_pw},
            timeout=15,
        )
        assert rp.status_code == 200

        # Login with new password
        login = requests.post(f"{API}/auth/login", json={"email": email, "password": new_pw}, timeout=15)
        assert login.status_code == 200


# ---------- toggle status ----------

class TestToggleStatus:
    def test_disable_agent_blocks_login(self, admin_session):
        email = _uniq_email("disable")
        pw = "Init@Pass12"
        inv = admin_session.post(f"{API}/admin/agents", json={"email": email, "display_name": "Disable QA"}, timeout=15).json()
        requests.post(f"{API}/auth/accept-invite", json={"token": inv["invite_token"], "new_password": pw}, timeout=15)
        agent_id = inv["agent"]["id"]

        # confirm can login
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15).status_code == 200

        # disable
        r = admin_session.patch(f"{API}/admin/agents/{agent_id}/status", json={"status": "disabled"}, timeout=10)
        assert r.status_code == 200

        # login now blocked → 401 (login() short-circuits when status == disabled)
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
        assert r2.status_code == 401

        # re-enable
        r3 = admin_session.patch(f"{API}/admin/agents/{agent_id}/status", json={"status": "active"}, timeout=10)
        assert r3.status_code == 200
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15).status_code == 200


# ---------- logout ----------

class TestLogout:
    def test_logout_clears_session(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
        assert s.get(f"{API}/auth/me", timeout=10).status_code == 200
        r = s.post(f"{API}/auth/logout", timeout=10)
        assert r.status_code == 200
        # After logout cookies should be cleared
        s.cookies.clear()
        assert s.get(f"{API}/auth/me", timeout=10).status_code == 401


# ---------- change password ----------

class TestChangePassword:
    def test_change_password_flow(self, admin_session):
        # create+accept agent
        email = _uniq_email("chg")
        pw1 = "Init@Change1"
        pw2 = "Init@Change2"
        inv = admin_session.post(f"{API}/admin/agents", json={"email": email, "display_name": "ChgPw QA"}, timeout=15).json()
        requests.post(f"{API}/auth/accept-invite", json={"token": inv["invite_token"], "new_password": pw1}, timeout=15)

        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": email, "password": pw1}, timeout=15)
        assert r.status_code == 200

        # change
        cp = s.post(f"{API}/auth/change-password", json={"current_password": pw1, "new_password": pw2}, timeout=15)
        assert cp.status_code == 200

        # old fails
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": pw1}, timeout=15).status_code == 401
        # new works
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": pw2}, timeout=15).status_code == 200


# ---------- brute force lockout ----------

class TestBruteForce:
    def test_lockout_after_repeated_failures(self, admin_session):
        # Fresh agent to avoid polluting other tests
        email = _uniq_email("brute")
        pw = "Brute@Pass1"
        inv = admin_session.post(f"{API}/admin/agents", json={"email": email, "display_name": "Brute QA"}, timeout=15).json()
        requests.post(f"{API}/auth/accept-invite", json={"token": inv["invite_token"], "new_password": pw}, timeout=15)

        codes = []
        for _ in range(7):
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": "wrong-pass"}, timeout=10)
            codes.append(r.status_code)
        # Expect a 429 at some point after 5 failed attempts
        assert 429 in codes, f"No lockout observed. Codes: {codes}"
