"""Phase 5 — Agent Portal API tests.

Covers: dashboard, catalog + markups (bounds, audit, draft 404), admin markup
settings interplay (out_of_range / bookable), fund requests (bounds, max 5
pending, admin queue), ledger + transactions, profile, RBAC.
Cleans up TEST_P5 fund requests, demo-agent markups, and restores settings.
"""
import os
from decimal import Decimal

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("yongmichael992@gmail.com", "Admin@12345")
AGENT = ("agent.demo@biyahetabai.example.com", "Agent@12345")
DRAFT_PKG = "447babf3-15ab-4506-b313-0d17c2e325be"
REF_PREFIX = "TEST_P5"


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def agent():
    return _login(*AGENT)


@pytest.fixture(scope="module", autouse=True)
def cleanup(db, admin, agent):
    prof = agent.get(f"{API}/agent/dashboard", timeout=15)
    existing_markups = {m["_id"] for m in db.agent_package_markups.find({}, {"_id": 1})}
    markup_values = {m["_id"]: m["markup_amount"] for m in db.agent_package_markups.find({})}
    yield
    db.fund_requests.delete_many({"reference_no": {"$regex": f"^{REF_PREFIX}"}})
    db.agent_package_markups.delete_many({"_id": {"$nin": list(existing_markups)}})
    for mid, val in markup_values.items():
        db.agent_package_markups.update_one({"_id": mid}, {"$set": {"markup_amount": val}})
    admin.put(f"{API}/admin/settings/maximum_markup_amount", json={"value": "10000.00"}, timeout=15)
    admin.put(f"{API}/admin/settings/minimum_markup_amount", json={"value": "0.00"}, timeout=15)


@pytest.fixture(scope="module")
def pkg_id(agent):
    r = agent.get(f"{API}/agent/packages", timeout=15)
    return r.json()["packages"][0]["id"]


# --- RBAC ---
class TestRBAC:
    @pytest.mark.parametrize("path", ["dashboard", "packages", "fund-requests", "ledger", "transactions", "profile"])
    def test_anon_401(self, path):
        assert requests.get(f"{API}/agent/{path}", timeout=15).status_code == 401

    @pytest.mark.parametrize("path", ["dashboard", "packages", "profile"])
    def test_admin_403(self, admin, path):
        assert admin.get(f"{API}/agent/{path}", timeout=15).status_code == 403

    def test_agent_cannot_admin(self, agent):
        for p in ["settings", "fund-requests", "agents"]:
            assert agent.get(f"{API}/admin/{p}", timeout=15).status_code == 403, p


# --- Dashboard ---
class TestDashboard:
    def test_shape(self, agent):
        r = agent.get(f"{API}/agent/dashboard", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["booking_balance", "total_earned", "bookings_total", "pending_fund_requests",
                  "packages_needing_markup", "markup_bounds", "recent_ledger", "agent"]:
            assert k in d, k
        assert isinstance(d["bookings_total"], int)
        Decimal(d["booking_balance"])


# --- Catalog + markup ---
class TestCatalog:
    def test_published_only(self, agent, db):
        r = agent.get(f"{API}/agent/packages", timeout=15)
        assert r.status_code == 200
        pk = r.json()["packages"]
        published = db.packages.count_documents({"status": "published"})
        assert len(pk) == published
        assert DRAFT_PKG not in [p["id"] for p in pk]
        for p in pk:
            for k in ["net_cost", "bonus_commission", "markup_amount", "retail_price", "markup_status", "bookable"]:
                assert k in p
            assert p["markup_status"] in ("unset", "ok", "out_of_range")
            if p["markup_status"] == "unset":
                assert p["bookable"] is False and p["retail_price"] is None

    def test_search(self, agent):
        r = agent.get(f"{API}/agent/packages", params={"q": "osaka"}, timeout=15)
        assert r.status_code == 200
        assert all("osaka" in p["title"].lower() for p in r.json()["packages"])
        assert len(r.json()["packages"]) >= 1

    def test_draft_detail_404(self, agent):
        assert agent.get(f"{API}/agent/packages/{DRAFT_PKG}", timeout=15).status_code == 404
        r = agent.put(f"{API}/agent/packages/{DRAFT_PKG}/markup", json={"markup_amount": "100"}, timeout=15)
        assert r.status_code == 404

    def test_set_markup_and_persist(self, agent, admin, pkg_id):
        r = agent.put(f"{API}/agent/packages/{pkg_id}/markup", json={"markup_amount": "1500.5"}, timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()["package"]
        assert p["markup_amount"] == "1500.50"
        assert Decimal(p["retail_price"]) == Decimal(p["net_cost"]) + Decimal("1500.50")
        assert p["markup_status"] == "ok" and p["bookable"] is True
        g = agent.get(f"{API}/agent/packages/{pkg_id}", timeout=15).json()["package"]
        assert g["markup_amount"] == "1500.50"
        # update existing (upsert path)
        r = agent.put(f"{API}/agent/packages/{pkg_id}/markup", json={"markup_amount": 2000}, timeout=15)
        assert r.json()["package"]["markup_amount"] == "2000.00"
        al = admin.get(f"{API}/admin/audit-logs", params={"action": "agent.markup.set"}, timeout=15)
        assert al.status_code == 200
        body = al.json()
        rows = body.get("audit_logs") or body.get("items") or body.get("logs") or []
        assert any((x.get("after") or {}).get("package_id") == pkg_id for x in rows), str(body)[:300]

    def test_markup_out_of_bounds(self, agent, pkg_id):
        r = agent.put(f"{API}/agent/packages/{pkg_id}/markup", json={"markup_amount": "10000.01"}, timeout=15)
        assert r.status_code == 400
        r = agent.put(f"{API}/agent/packages/{pkg_id}/markup", json={"markup_amount": "-1"}, timeout=15)
        assert r.status_code == 422

    def test_admin_narrow_range_flags_out_of_range(self, agent, admin, pkg_id):
        agent.put(f"{API}/agent/packages/{pkg_id}/markup", json={"markup_amount": "2000"}, timeout=15)
        # cross-key rule
        bad = admin.put(f"{API}/admin/settings/minimum_markup_amount", json={"value": "20000"}, timeout=15)
        assert bad.status_code == 400
        r = admin.put(f"{API}/admin/settings/maximum_markup_amount", json={"value": "1000"}, timeout=15)
        assert r.status_code == 200, r.text
        try:
            bad2 = admin.put(f"{API}/admin/settings/minimum_markup_amount", json={"value": "1500"}, timeout=15)
            assert bad2.status_code == 400
            p = agent.get(f"{API}/agent/packages/{pkg_id}", timeout=15).json()["package"]
            assert p["markup_status"] == "out_of_range" and p["bookable"] is False
            lst = agent.get(f"{API}/agent/packages", timeout=15).json()
            assert lst["markup_bounds"]["max"] == "1000.00"
            d = agent.get(f"{API}/agent/dashboard", timeout=15).json()
            assert d["packages_needing_markup"] >= 1
            r2 = agent.put(f"{API}/agent/packages/{pkg_id}/markup", json={"markup_amount": "2000"}, timeout=15)
            assert r2.status_code == 400
            r3 = agent.put(f"{API}/agent/packages/{pkg_id}/markup", json={"markup_amount": "800"}, timeout=15)
            assert r3.status_code == 200 and r3.json()["package"]["bookable"] is True
        finally:
            admin.put(f"{API}/admin/settings/maximum_markup_amount", json={"value": "10000.00"}, timeout=15)
        s = admin.get(f"{API}/admin/settings", timeout=15).json()["settings"]
        assert s["maximum_markup_amount"]["value"] == "10000.00"
        assert s["minimum_markup_amount"]["value"] == "0.00"


# --- Fund requests ---
class TestFundRequests:
    def test_list(self, agent):
        r = agent.get(f"{API}/agent/fund-requests", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["topup_bounds"] == {"min": "100.00", "max": "1000000.00"}
        assert isinstance(d["fund_requests"], list)

    def test_bounds(self, agent):
        assert agent.post(f"{API}/agent/fund-requests", json={"amount": "99.99"}, timeout=15).status_code == 400
        assert agent.post(f"{API}/agent/fund-requests", json={"amount": "1000000.01"}, timeout=15).status_code == 400
        assert agent.post(f"{API}/agent/fund-requests", json={"amount": "0"}, timeout=15).status_code == 422

    def test_create_and_admin_queue_and_max_pending(self, agent, admin, db):
        r = agent.post(f"{API}/agent/fund-requests",
                       json={"amount": "500", "reference_no": f"{REF_PREFIX}-1", "note": "  hi  "}, timeout=15)
        assert r.status_code == 200, r.text
        fr = r.json()["fund_request"]
        assert fr["status"] == "pending" and fr["amount"] == "500.00" and fr["note"] == "hi"
        mine = agent.get(f"{API}/agent/fund-requests", timeout=15).json()["fund_requests"]
        assert fr["id"] in [x["id"] for x in mine]
        q = admin.get(f"{API}/admin/fund-requests", params={"status": "pending", "page_size": 100}, timeout=15).json()
        assert fr["id"] in [x["id"] for x in q["fund_requests"]]
        # fill up to 5 pending
        pending = agent.get(f"{API}/agent/dashboard", timeout=15).json()["pending_fund_requests"]
        i = 2
        while pending < 5:
            rr = agent.post(f"{API}/agent/fund-requests",
                            json={"amount": "100", "reference_no": f"{REF_PREFIX}-{i}"}, timeout=15)
            assert rr.status_code == 200
            pending += 1
            i += 1
        rr = agent.post(f"{API}/agent/fund-requests",
                        json={"amount": "100", "reference_no": f"{REF_PREFIX}-x"}, timeout=15)
        assert rr.status_code == 409


# --- Ledger + transactions ---
class TestLedger:
    def test_ledger(self, agent):
        r = agent.get(f"{API}/agent/ledger", timeout=15)
        assert r.status_code == 200
        d = r.json()
        live = [x for x in d["rows"] if x["status"] != "cancelled"]
        for x in d["rows"]:
            if x["status"] == "cancelled":
                assert x["earned"] == "0.00"
        assert Decimal(d["totals"]["earned"]) == sum((Decimal(x["earned"]) for x in live), Decimal("0"))
        assert Decimal(d["totals"]["net_cost"]) == sum((Decimal(x["net_cost"]) for x in live), Decimal("0"))

    def test_transactions(self, agent):
        r = agent.get(f"{API}/agent/transactions", timeout=15)
        assert r.status_code == 200
        for t in r.json()["transactions"]:
            assert "amount" in t and "balance_after" in t


# --- Profile ---
class TestProfile:
    def test_get_patch(self, agent):
        orig = agent.get(f"{API}/agent/profile", timeout=15).json()["profile"]
        assert orig["email"] == AGENT[0]
        r = agent.patch(f"{API}/agent/profile",
                        json={"phone": "+63 917 000 TEST", "address": "TEST addr", "display_name": "HACK",
                              "email": "x@x.com"}, timeout=15)
        assert r.status_code == 200
        p = r.json()["profile"]
        assert p["phone"] == "+63 917 000 TEST" and p["address"] == "TEST addr"
        g = agent.get(f"{API}/agent/profile", timeout=15).json()["profile"]
        assert g["display_name"] == orig["display_name"] and g["email"] == orig["email"]
        assert g["phone"] == "+63 917 000 TEST"
        agent.patch(f"{API}/agent/profile", json={"phone": orig["phone"] or "", "address": orig["address"] or ""},
                    timeout=15)

    def test_patch_too_long(self, agent):
        r = agent.patch(f"{API}/agent/profile", json={"phone": "1" * 41}, timeout=15)
        assert r.status_code == 422
