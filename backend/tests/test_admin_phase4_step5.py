"""Phase 4 Step 5 tests: Transactions ledger + CSV, Contacts inbox, Settings, Audit logs.

- RBAC on all four routers (401 anon, 403 agent)
- Transactions list + filters + CSV export headers/columns
- Contacts list (status + q + new_count), GET auto-flips new→read, PATCH audit + no-op
- Settings: 4 keys, PUT validation, cross-key rule, brand rules, bool coercion,
  min/max drive fund-requests (reverted at end)
- Audit logs list w/ filters + prefix regex, /actions distinct
- Regression smoke on prior admin endpoints
"""
from __future__ import annotations

import os
import uuid
from decimal import Decimal

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
    if isinstance(agents, dict):
        agents = agents.get("items", [])
    for a in agents:
        email = (a.get("email") or a.get("user", {}).get("email") or "").lower()
        if email == DEMO_AGENT_EMAIL:
            return a.get("id") or a.get("_id") or a.get("agent_id")
    pytest.skip("demo agent id not found")


# ---------- RBAC ----------

ADMIN_PATHS_GET = [
    "/admin/transactions",
    "/admin/transactions/export.csv",
    "/admin/contacts",
    "/admin/settings",
    "/admin/audit-logs",
    "/admin/audit-logs/actions",
]


class TestRBAC:
    @pytest.mark.parametrize("path", ADMIN_PATHS_GET)
    def test_anon_401(self, path):
        r = requests.get(f"{API}{path}", timeout=10)
        assert r.status_code == 401, f"{path}: {r.status_code}"

    @pytest.mark.parametrize("path", ADMIN_PATHS_GET)
    def test_agent_403(self, agent_sess, path):
        r = agent_sess.get(f"{API}{path}", timeout=10)
        assert r.status_code == 403, f"{path}: {r.status_code}"

    def test_agent_put_setting_403(self, agent_sess):
        r = agent_sess.put(f"{API}/admin/settings/brand", json={"value": {"name": "X"}}, timeout=10)
        assert r.status_code == 403

    def test_agent_patch_contact_403(self, agent_sess):
        r = agent_sess.patch(f"{API}/admin/contacts/anything", json={"status": "read"}, timeout=10)
        assert r.status_code == 403


# ---------- Transactions ----------

class TestTransactions:
    def test_list_shape(self, admin):
        r = admin.get(f"{API}/admin/transactions", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "transactions" in data and "total" in data
        if data["transactions"]:
            row = data["transactions"][0]
            for k in ("id", "created_at", "agent_id", "agent", "account_kind",
                      "type", "amount", "balance_after"):
                assert k in row, f"missing key {k}"
            if row["agent"]:
                for k in ("id", "display_name", "agency_name"):
                    assert k in row["agent"]

    def test_filter_account_kind_booking(self, admin):
        r = admin.get(f"{API}/admin/transactions?account_kind=booking", timeout=15)
        assert r.status_code == 200
        for row in r.json()["transactions"]:
            assert row["account_kind"] == "booking"

    def test_filter_unknown_type_400(self, admin):
        r = admin.get(f"{API}/admin/transactions?type=nope_bogus", timeout=15)
        assert r.status_code == 400, r.text

    def test_filter_by_agent(self, admin, demo_agent_id):
        r = admin.get(f"{API}/admin/transactions?agent_id={demo_agent_id}", timeout=15)
        assert r.status_code == 200
        for row in r.json()["transactions"]:
            assert row["agent_id"] == demo_agent_id

    def test_date_filter_no_error(self, admin):
        r = admin.get(f"{API}/admin/transactions?date_from=2020-01-01&date_to=2099-12-31", timeout=15)
        assert r.status_code == 200

    def test_csv_export_headers(self, admin):
        r = admin.get(f"{API}/admin/transactions/export.csv", timeout=20)
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("content-type", "")
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        first_line = r.text.splitlines()[0]
        expected = ("created_at,agent_id,agent_display_name,agency_name,"
                    "account_kind,type,amount,balance_after,ref_type,ref_id,note")
        assert first_line == expected, f"got: {first_line}"


# ---------- Contacts ----------

def _seed_contact(subject_prefix="TEST_CONTACT"):
    """Submit a contact through the public endpoint if it exists."""
    subj = f"{subject_prefix}_{uuid.uuid4().hex[:6]}"
    payload = {
        "name": "Pytest Tester",
        "email": "pytest@example.com",
        "subject": subj,
        "message": "This is a pytest-generated contact message for testing.",
    }
    # try common public endpoints
    for path in ("/public/contact", "/public/contacts", "/contact-messages"):
        r = requests.post(f"{API}{path}", json=payload, timeout=10)
        if r.status_code in (200, 201):
            return subj
    return None  # relies on existing seed data


class TestContacts:
    def test_list_and_new_count(self, admin):
        r = admin.get(f"{API}/admin/contacts", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "contacts" in data and "new_count" in data
        assert isinstance(data["contacts"], list)

    def test_status_filter(self, admin):
        r = admin.get(f"{API}/admin/contacts?status=new", timeout=15)
        assert r.status_code == 200
        for row in r.json()["contacts"]:
            assert row["status"] == "new"

    def test_q_search(self, admin):
        r = admin.get(f"{API}/admin/contacts?q=zzz_no_match_expected_xyz", timeout=15)
        assert r.status_code == 200

    def test_get_flips_new_to_read(self, admin):
        # Try to find a 'new' one; if none, seed and re-fetch
        r = admin.get(f"{API}/admin/contacts?status=new", timeout=15)
        rows = r.json()["contacts"]
        if not rows:
            _seed_contact()
            r = admin.get(f"{API}/admin/contacts?status=new", timeout=15)
            rows = r.json()["contacts"]
            if not rows:
                pytest.skip("No 'new' contact available to test auto-flip")

        cid = rows[0]["id"]
        # First GET flips to read
        r1 = admin.get(f"{API}/admin/contacts/{cid}", timeout=15)
        assert r1.status_code == 200, r1.text
        assert r1.json()["contact"]["status"] == "read"
        # Second GET stays read
        r2 = admin.get(f"{API}/admin/contacts/{cid}", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["contact"]["status"] == "read"

    def test_patch_noop(self, admin):
        r = admin.get(f"{API}/admin/contacts", timeout=15)
        rows = r.json()["contacts"]
        if not rows:
            pytest.skip("No contact to patch")
        cid = rows[0]["id"]
        cur_status = rows[0]["status"]
        # no-op patch (same status)
        r2 = admin.patch(f"{API}/admin/contacts/{cid}", json={"status": cur_status}, timeout=15)
        assert r2.status_code == 200
        body = r2.json()
        assert body.get("ok") is True and body.get("changed") is False

    def test_patch_writes_audit(self, admin):
        r = admin.get(f"{API}/admin/contacts", timeout=15)
        rows = r.json()["contacts"]
        if not rows:
            pytest.skip("No contact to patch")
        cid = rows[0]["id"]
        # cycle status via a distinct value
        new_status = "responded" if rows[0]["status"] != "responded" else "archived"
        note = f"pytest-note-{uuid.uuid4().hex[:6]}"
        r2 = admin.patch(f"{API}/admin/contacts/{cid}",
                         json={"status": new_status, "internal_note": note}, timeout=15)
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body.get("changed") is True

        # Verify audit log has contact.update entry for this target_id
        alr = admin.get(f"{API}/admin/audit-logs?action=contact.update&target_id={cid}", timeout=15)
        assert alr.status_code == 200
        rows2 = alr.json()["audit_logs"]
        assert any(r_.get("target_id") == cid for r_ in rows2)


# ---------- Settings ----------

class TestSettings:
    def test_list_has_four_keys(self, admin):
        r = admin.get(f"{API}/admin/settings", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()["settings"]
        expected = {"brand", "minimum_topup_amount", "maximum_topup_amount",
                    "commission_withdrawals_enabled"}
        assert set(data.keys()) == expected
        for k, v in data.items():
            for field in ("key", "label", "kind", "description", "value", "updated_at"):
                assert field in v, f"{k} missing {field}"

    def test_put_unknown_key_404(self, admin):
        r = admin.put(f"{API}/admin/settings/nope_missing",
                      json={"value": "x"}, timeout=15)
        assert r.status_code == 404, r.text

    def test_bool_coercion(self, admin):
        for v in [True, False, "true", "false"]:
            r = admin.put(f"{API}/admin/settings/commission_withdrawals_enabled",
                          json={"value": v}, timeout=15)
            assert r.status_code == 200, f"{v}: {r.text}"

    def test_brand_requires_object(self, admin):
        r = admin.put(f"{API}/admin/settings/brand",
                      json={"value": "not-an-object"}, timeout=15)
        assert r.status_code == 400

    def test_brand_name_required(self, admin):
        r = admin.put(f"{API}/admin/settings/brand",
                      json={"value": {"name": "  ", "tagline": "x"}}, timeout=15)
        assert r.status_code == 400

    def test_brand_strips_extra_keys(self, admin):
        r = admin.put(
            f"{API}/admin/settings/brand",
            json={"value": {"name": "BiyaheTaBai", "tagline": "Test tagline",
                            "currency": "PHP", "support_email": "s@x.com",
                            "support_phone": "+63", "evil_extra": "should-be-stripped"}},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        r2 = admin.get(f"{API}/admin/settings", timeout=15)
        brand_val = r2.json()["settings"]["brand"]["value"]
        assert "evil_extra" not in brand_val
        assert brand_val.get("name") == "BiyaheTaBai"

    def test_cross_key_min_cannot_exceed_max(self, admin):
        # Read current max
        cur = admin.get(f"{API}/admin/settings", timeout=15).json()["settings"]
        cur_max = cur["maximum_topup_amount"]["value"] or "1000000.00"
        too_big = str(Decimal(str(cur_max)) + Decimal("1"))
        r = admin.put(f"{API}/admin/settings/minimum_topup_amount",
                      json={"value": too_big}, timeout=15)
        assert r.status_code == 400, r.text

    def test_cross_key_max_below_min(self, admin):
        cur = admin.get(f"{API}/admin/settings", timeout=15).json()["settings"]
        cur_min = cur["minimum_topup_amount"]["value"] or "100.00"
        too_small = str(max(Decimal("1"), Decimal(str(cur_min)) - Decimal("1")))
        # Only meaningful if cur_min > 1
        if Decimal(str(cur_min)) > Decimal("1"):
            r = admin.put(f"{API}/admin/settings/maximum_topup_amount",
                          json={"value": too_small}, timeout=15)
            assert r.status_code == 400, r.text

    def test_settings_drive_fund_requests_and_revert(self, admin, demo_agent_id):
        # PUT minimum=500
        r = admin.put(f"{API}/admin/settings/minimum_topup_amount",
                      json={"value": "500"}, timeout=15)
        assert r.status_code == 200, r.text
        try:
            # 499 should now fail
            r1 = admin.post(f"{API}/admin/fund-requests",
                            json={"agent_id": demo_agent_id, "amount": "499"}, timeout=15)
            assert r1.status_code == 400, r1.text
            # 500 should succeed
            r2 = admin.post(
                f"{API}/admin/fund-requests",
                json={"agent_id": demo_agent_id, "amount": "500",
                      "reference_no": f"TEST-BOUND-{uuid.uuid4().hex[:6]}",
                      "note": "pytest bounds"},
                timeout=15,
            )
            assert r2.status_code == 200, r2.text
            # Clean up: reject that pending request so it doesn't clutter
            fid = r2.json()["fund_request"]["id"]
            admin.post(f"{API}/admin/fund-requests/{fid}/reject",
                       json={"decision_note": "pytest cleanup"}, timeout=15)
        finally:
            # ALWAYS revert min to 100
            r3 = admin.put(f"{API}/admin/settings/minimum_topup_amount",
                           json={"value": "100"}, timeout=15)
            assert r3.status_code == 200, f"REVERT FAILED: {r3.text}"

    def test_settings_audit_log_written(self, admin):
        # trigger a change
        admin.put(f"{API}/admin/settings/commission_withdrawals_enabled",
                  json={"value": True}, timeout=15)
        r = admin.get(f"{API}/admin/audit-logs?action=settings.update", timeout=15)
        assert r.status_code == 200
        rows = r.json()["audit_logs"]
        assert any(row.get("action") == "settings.update" for row in rows)


# ---------- Audit logs ----------

class TestAuditLogs:
    def test_list_shape(self, admin):
        r = admin.get(f"{API}/admin/audit-logs", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "audit_logs" in data and "total" in data

    def test_action_exact_filter(self, admin):
        r = admin.get(f"{API}/admin/audit-logs?action=settings.update", timeout=15)
        assert r.status_code == 200
        for row in r.json()["audit_logs"]:
            assert row["action"] == "settings.update"

    def test_action_prefix_regex(self, admin):
        r = admin.get(f"{API}/admin/audit-logs?action=fund_request.", timeout=15)
        assert r.status_code == 200
        for row in r.json()["audit_logs"]:
            assert row["action"].startswith("fund_request.")

    def test_actor_resolution(self, admin):
        r = admin.get(f"{API}/admin/audit-logs?page_size=5", timeout=15)
        assert r.status_code == 200
        for row in r.json()["audit_logs"]:
            if row.get("actor_user_id"):
                # actor may be resolved or None if user missing
                if row["actor"]:
                    assert "email" in row["actor"]
                    assert "id" in row["actor"]

    def test_actions_endpoint(self, admin):
        r = admin.get(f"{API}/admin/audit-logs/actions", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "actions" in data and "target_types" in data
        assert data["actions"] == sorted(data["actions"])
        assert data["target_types"] == sorted(data["target_types"])
        assert all(a is not None for a in data["actions"])
        assert all(t is not None for t in data["target_types"])


# ---------- Regression smoke ----------

class TestRegression:
    def test_dashboard(self, admin):
        r = admin.get(f"{API}/admin/dashboard", timeout=15)
        # dashboard may be /admin/dashboard or a summary path
        assert r.status_code in (200, 404)

    def test_agents(self, admin):
        r = admin.get(f"{API}/admin/agents", timeout=15)
        assert r.status_code == 200

    def test_packages(self, admin):
        r = admin.get(f"{API}/admin/packages", timeout=15)
        assert r.status_code == 200

    def test_bookings(self, admin):
        r = admin.get(f"{API}/admin/bookings", timeout=15)
        assert r.status_code == 200

    def test_fund_requests(self, admin):
        r = admin.get(f"{API}/admin/fund-requests", timeout=15)
        assert r.status_code == 200
