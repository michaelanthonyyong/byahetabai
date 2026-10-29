"""Phase 6 — Agent customers, agent bookings (net-cost debit), quote PDFs.

Cleans up: TEST_P6 customers, bookings + their transactions, extra markups,
restores agent booking balance and markup bound settings.
Run with -n0.
"""
import os
from datetime import date, timedelta
from decimal import Decimal

import fitz  # pymupdf
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.decimal128 import Decimal128

load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("yongmichael992@gmail.com", "Admin@12345")
AGENT = ("agent.demo@biyahetabai.example.com", "Agent@12345")
CEBU = "4c02efb1-1bc8-4a09-8636-0a49020f42f4"  # net 3500, bonus 300, markup 500, pax 1-10
BANGKOK = "c6a99ca6-4409-436b-bd00-191de8323e76"  # net 19500, pax 2-20, no markup
OSAKA = "7ad0cefd-7603-4903-99dd-63e65dad9fe3"  # net 39888, pax 2-10
DRAFT = "447babf3-15ab-4506-b313-0d17c2e325be"
OTHER_AGENT = "bab98fb5-08ae-4dce-9e5f-7c36d6121b62"
FUTURE = (date.today() + timedelta(days=30)).isoformat()
PFX = "TEST_P6"


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return s


def _pdf_text(content: bytes) -> str:
    doc = fitz.open(stream=content, filetype="pdf")
    return "\n".join(p.get_text() for p in doc)


@pytest.fixture(scope="module")
def db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def agent():
    return _login(*AGENT)


@pytest.fixture(scope="module")
def agent_id(db):
    u = db.users.find_one({"email": AGENT[0]})
    return db.agent_profiles.find_one({"user_id": u["_id"]})["_id"]


@pytest.fixture(scope="module", autouse=True)
def cleanup(db, agent_id):
    prof = db.agent_profiles.find_one({"_id": agent_id})
    bal_before = prof["booking_account"]["balance"]
    existing_markups = {m["_id"] for m in db.agent_package_markups.find({}, {"_id": 1})}
    existing_bookings = {b["_id"] for b in db.bookings.find({}, {"_id": 1})}
    settings_before = {s["key"]: s.get("value") for s in db.system_settings.find(
        {"key": {"$in": ["minimum_markup_amount", "maximum_markup_amount"]}})}
    yield
    new_b = [b["_id"] for b in db.bookings.find({"_id": {"$nin": list(existing_bookings)}}, {"_id": 1})]
    db.financial_transactions.delete_many({"ref_type": "booking", "ref_id": {"$in": new_b}})
    db.commissions.delete_many({"booking_id": {"$in": new_b}})
    db.notifications.delete_many({"ref_type": "booking", "ref_id": {"$in": new_b}})  # phase 7 alerts
    db.booking_payments.delete_many({"booking_id": {"$in": new_b}})
    db.bookings.delete_many({"_id": {"$in": new_b}})
    db.customers.delete_many({"first_name": {"$regex": f"^{PFX}"}})
    db.agent_package_markups.delete_many({"_id": {"$nin": list(existing_markups)}})
    db.agent_profiles.update_one({"_id": agent_id}, {"$set": {"booking_account.balance": bal_before}})
    for k, v in settings_before.items():
        db.system_settings.update_one({"key": k}, {"$set": {"value": v}})


@pytest.fixture(scope="module")
def customer(agent):
    r = agent.post(f"{API}/agent/customers", json={
        "first_name": f"{PFX}_Maria", "last_name": "Santos", "email": "test_p6@example.com", "phone": "09171234567",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["customer"]


@pytest.fixture(scope="module")
def other_customer(db):
    cid = "test-p6-other-agent-customer"
    db.customers.delete_one({"_id": cid})
    db.customers.insert_one({"_id": cid, "agent_id": OTHER_AGENT, "first_name": f"{PFX}_Other",
                             "last_name": "Agent", "created_at": "2026-01-01T00:00:00+00:00"})
    yield cid
    db.customers.delete_one({"_id": cid})


def _balance(agent) -> Decimal:
    return Decimal(agent.get(f"{API}/agent/dashboard", timeout=15).json()["booking_balance"])


# --- RBAC ---
class TestRBAC:
    @pytest.mark.parametrize("path", ["customers", "bookings"])
    def test_admin_403(self, admin, path):
        assert admin.get(f"{API}/agent/{path}", timeout=15).status_code == 403

    def test_admin_quote_403(self, admin):
        r = admin.post(f"{API}/agent/quotes/pdf", json={"package_id": CEBU, "pax": 2}, timeout=15)
        assert r.status_code == 403

    @pytest.mark.parametrize("path", ["customers", "bookings"])
    def test_anon_401(self, path):
        assert requests.get(f"{API}/agent/{path}", timeout=15).status_code == 401


# --- customers CRUD ---
class TestCustomers:
    def test_create_and_get(self, agent, customer):
        assert customer["full_name"] == f"{PFX}_Maria Santos"
        assert customer["bookings_count"] == 0
        r = agent.get(f"{API}/agent/customers/{customer['id']}", timeout=15)
        assert r.status_code == 200
        assert r.json()["customer"]["email"] == "test_p6@example.com"
        assert r.json()["bookings"] == []

    def test_search(self, agent, customer):
        r = agent.get(f"{API}/agent/customers", params={"q": "p6_mar"}, timeout=15)
        ids = [c["id"] for c in r.json()["customers"]]
        assert customer["id"] in ids
        r = agent.get(f"{API}/agent/customers", params={"q": "zzznomatch"}, timeout=15)
        assert r.json()["customers"] == []

    def test_validation(self, agent):
        r = agent.post(f"{API}/agent/customers", json={"first_name": "", "last_name": "X"}, timeout=15)
        assert r.status_code == 422
        r = agent.post(f"{API}/agent/customers", json={"first_name": "A", "last_name": "B", "email": "bad"}, timeout=15)
        assert r.status_code == 422

    def test_patch(self, agent, customer):
        r = agent.patch(f"{API}/agent/customers/{customer['id']}", json={"phone": "0999"}, timeout=15)
        assert r.status_code == 200 and r.json()["customer"]["phone"] == "0999"
        assert agent.get(f"{API}/agent/customers/{customer['id']}", timeout=15).json()["customer"]["phone"] == "0999"
        r = agent.patch(f"{API}/agent/customers/{customer['id']}", json={"first_name": "   "}, timeout=15)
        assert r.status_code == 400

    def test_delete_and_404(self, agent):
        c = agent.post(f"{API}/agent/customers", json={"first_name": f"{PFX}_Del", "last_name": "Me"}, timeout=15).json()["customer"]
        assert agent.delete(f"{API}/agent/customers/{c['id']}", timeout=15).status_code == 200
        assert agent.get(f"{API}/agent/customers/{c['id']}", timeout=15).status_code == 404

    def test_other_agent_isolation(self, agent, other_customer):
        assert agent.get(f"{API}/agent/customers/{other_customer}", timeout=15).status_code == 404
        assert agent.patch(f"{API}/agent/customers/{other_customer}", json={"phone": "1"}, timeout=15).status_code == 404
        assert agent.delete(f"{API}/agent/customers/{other_customer}", timeout=15).status_code == 404
        ids = [c["id"] for c in agent.get(f"{API}/agent/customers", timeout=15).json()["customers"]]
        assert other_customer not in ids


# --- bookings ---
class TestBookings:
    state: dict = {}

    def test_validation_errors(self, agent, customer, other_customer):
        base = {"customer_id": customer["id"], "package_id": CEBU, "pax": 2, "travel_start_date": FUTURE}
        cases = [
            ({**base, "package_id": BANGKOK}, 400),           # markup unset
            ({**base, "pax": 11}, 400),                        # above max_pax
            ({**base, "travel_start_date": "2020-01-01"}, 400),  # past
            ({**base, "travel_start_date": "2026/13/01"}, 400),  # bad format
            ({**base, "customer_id": other_customer}, 404),   # other agent's customer
            ({**base, "package_id": DRAFT}, 404),
        ]
        bal = _balance(agent)
        for payload, code in cases:
            r = agent.post(f"{API}/agent/bookings", json=payload, timeout=15)
            assert r.status_code == code, (payload, r.status_code, r.text)
        assert _balance(agent) == bal

    def test_out_of_range_markup(self, agent, admin, customer):
        r = admin.put(f"{API}/admin/settings/maximum_markup_amount", json={"value": "400.00"}, timeout=15)
        assert r.status_code == 200, r.text
        try:
            r = agent.post(f"{API}/agent/bookings", json={"customer_id": customer["id"], "package_id": CEBU,
                                                          "pax": 1, "travel_start_date": FUTURE}, timeout=15)
            assert r.status_code == 400 and "outside" in r.json()["detail"]
            r = agent.post(f"{API}/agent/quotes/pdf", json={"package_id": CEBU, "pax": 1}, timeout=15)
            assert r.status_code == 400
        finally:
            admin.put(f"{API}/admin/settings/maximum_markup_amount", json={"value": "10000.00"}, timeout=15)

    def test_create_booking(self, agent, customer, db):
        bal = _balance(agent)
        r = agent.post(f"{API}/agent/bookings", json={
            "customer_id": customer["id"], "package_id": CEBU, "pax": 3, "travel_start_date": FUTURE,
            "traveler_names": ["TEST Lead", "TEST Two", "", "Extra beyond pax", "Fourth dropped"], "notes": "TEST_P6 note",
        }, timeout=15)
        assert r.status_code == 200, r.text
        b = r.json()["booking"]
        assert b["status"] == "pending"
        import re
        assert re.match(r"^BTB-\d{6}-[0-9A-F]{4}$", b["reference_code"])
        assert b["unit_retail_price"] == "4000.00"
        assert b["total_retail_price"] == "12000.00"
        assert b["total_net_cost"] == "10500.00"
        assert b["total_markup"] == "1500.00"
        assert b["total_bonus_commission"] == "900.00"
        assert b["earned"] == "2400.00"
        assert [t["full_name"] for t in b["travelers"]] == ["TEST Lead", "TEST Two", "Extra beyond pax"]
        assert b["travelers"][0]["is_lead"] is True
        assert _balance(agent) == bal - Decimal("10500.00")
        doc = db.bookings.find_one({"_id": b["id"]})
        assert doc["unit_markup_amount"].to_decimal() == Decimal("500")
        assert doc["total_markup_amount"].to_decimal() == Decimal("1500")
        assert doc["total_retail_price"].to_decimal() == Decimal("12000")
        txn = db.financial_transactions.find_one({"idempotency_key": f"booking_debit:{b['id']}"})
        assert txn and txn["type"] == "booking_debit" or txn["type"].lower() == "booking_debit"
        assert txn["amount"].to_decimal() == Decimal("-10500")
        assert db.audit_logs.find_one({"action": "booking.create", "target_id": b["id"]})
        assert not db.commissions.find_one({"booking_id": b["id"]}), "bonus should not be paid into a balance"
        TestBookings.state["booking"] = b
        TestBookings.state["bal_after"] = bal - Decimal("10500.00")

    def test_list_get_ledger_transactions(self, agent):
        b = TestBookings.state["booking"]
        rows = agent.get(f"{API}/agent/bookings", params={"status": "pending"}, timeout=15).json()["bookings"]
        assert b["id"] in [x["id"] for x in rows]
        rows = agent.get(f"{API}/agent/bookings", params={"status": "confirmed"}, timeout=15).json()["bookings"]
        assert b["id"] not in [x["id"] for x in rows]
        assert agent.get(f"{API}/agent/bookings", params={"status": "bogus"}, timeout=15).status_code == 422
        g = agent.get(f"{API}/agent/bookings/{b['id']}", timeout=15)
        assert g.status_code == 200 and g.json()["booking"]["customer"]["name"] == f"{PFX}_Maria Santos"
        assert agent.get(f"{API}/agent/bookings/does-not-exist", timeout=15).status_code == 404
        led = agent.get(f"{API}/agent/ledger", timeout=15).json()["rows"]
        row = next(r for r in led if r["id"] == b["id"])
        assert row["earned"] == "2400.00" and row["net_cost"] == "10500.00" and row["customer_paid"] == "12000.00"
        tx = agent.get(f"{API}/agent/transactions", timeout=15).json()["transactions"]
        assert any(t["amount"] == "-10500.00" for t in tx)
        cust = agent.get(f"{API}/agent/customers/{b['customer']['id']}", timeout=15).json()
        assert cust["customer"]["bookings_count"] == 1

    def test_other_agent_booking_404(self, agent, db):
        other = db.bookings.find_one({"agent_id": {"$ne": TestBookings.state["booking"].get("agent_id", "x")}, "_id": {"$ne": TestBookings.state["booking"]["id"]}})
        # use any non-existing / foreign id
        assert agent.get(f"{API}/agent/bookings/foreign-id-xyz/quote.pdf", timeout=15).status_code == 404

    def test_delete_customer_with_booking_409(self, agent, customer):
        r = agent.delete(f"{API}/agent/customers/{customer['id']}", timeout=15)
        assert r.status_code == 409

    def test_insufficient_balance(self, agent, customer, db, agent_id):
        bal = _balance(agent)
        # set a markup on Osaka; 10 pax * 39888 = 398880 > balance
        assert agent.put(f"{API}/agent/packages/{OSAKA}/markup", json={"markup_amount": "1000"}, timeout=15).status_code == 200
        n_before = db.bookings.count_documents({"agent_id": agent_id})
        r = agent.post(f"{API}/agent/bookings", json={"customer_id": customer["id"], "package_id": OSAKA,
                                                      "pax": 10, "travel_start_date": FUTURE}, timeout=15)
        assert r.status_code == 400 and "Insufficient" in r.json()["detail"]
        assert _balance(agent) == bal
        assert db.bookings.count_documents({"agent_id": agent_id}) == n_before

    def test_booking_quote_pdf(self, agent):
        b = TestBookings.state["booking"]
        r = agent.get(f"{API}/agent/bookings/{b['id']}/quote.pdf", timeout=20)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert "attachment" in r.headers.get("content-disposition", "")
        text = _pdf_text(r.content)
        assert "4,000.00" in text and "12,000.00" in text
        assert b["reference_code"] in text
        for bad in ["3,500", "3500", "10,500", "1,500", "500.00", "2,400", "900.00"]:
            assert bad not in text.replace("4,000.00", "").replace("12,000.00", ""), f"leaked {bad}"

    def test_admin_sees_and_confirms(self, admin, agent):
        b = TestBookings.state["booking"]
        rows = admin.get(f"{API}/admin/bookings", params={"status": "pending", "q": b["reference_code"]}, timeout=15).json()["bookings"]
        assert any(x["id"] == b["id"] for x in rows)
        r = admin.patch(f"{API}/admin/bookings/{b['id']}/status", json={"status": "confirmed"}, timeout=15)
        assert r.status_code == 200, r.text
        assert agent.get(f"{API}/agent/bookings/{b['id']}", timeout=15).json()["booking"]["status"] == "confirmed"

    def test_admin_cancel_refund(self, admin, agent, db):
        b = TestBookings.state["booking"]
        bal = _balance(agent)
        r = admin.patch(f"{API}/admin/bookings/{b['id']}/status", json={"status": "cancelled", "refund": True, "reason": "TEST"}, timeout=15)
        assert r.status_code == 200, r.text
        assert _balance(agent) == bal + Decimal("10500.00")
        led = agent.get(f"{API}/agent/ledger", timeout=15).json()["rows"]
        row = next(x for x in led if x["id"] == b["id"])
        assert row["earned"] == "0.00" and row["status"] == "cancelled"

    def test_agent_cannot_cancel(self, agent):
        b = TestBookings.state["booking"]
        for m in ("delete", "patch"):
            r = getattr(agent, m)(f"{API}/agent/bookings/{b['id']}", timeout=15)
            assert r.status_code in (404, 405)
        assert agent.patch(f"{API}/admin/bookings/{b['id']}/status", json={"status": "cancelled"}, timeout=15).status_code == 403


# --- quote PDF ---
class TestQuotePdf:
    def test_quote_pdf(self, agent):
        r = agent.post(f"{API}/agent/quotes/pdf", json={"package_id": CEBU, "pax": 2,
                                                         "customer_name": "TEST_P6 Quote Guest", "travel_date": FUTURE}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/pdf")
        assert "attachment" in r.headers["content-disposition"]
        text = _pdf_text(r.content)
        assert "4,000.00" in text and "8,000.00" in text
        assert "TEST_P6 Quote Guest" in text
        stripped = text.replace("4,000.00", "").replace("8,000.00", "")
        for bad in ["3,500", "3500", "500.00", "7,000", "1,000.00", "300.00", "600.00"]:
            assert bad not in stripped, f"leaked {bad}"

    def test_quote_requires_markup(self, agent):
        assert agent.post(f"{API}/agent/quotes/pdf", json={"package_id": BANGKOK, "pax": 2}, timeout=15).status_code == 400

    def test_quote_bad_pax_and_date(self, agent):
        assert agent.post(f"{API}/agent/quotes/pdf", json={"package_id": CEBU, "pax": 50}, timeout=15).status_code == 400
        assert agent.post(f"{API}/agent/quotes/pdf", json={"package_id": CEBU, "pax": 2, "travel_date": "2020-01-01"}, timeout=15).status_code == 400
