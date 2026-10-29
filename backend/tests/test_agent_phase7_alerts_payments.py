"""Phase 7 — Booking status alerts (agent notifications) + customer payment tracking.

Cleans up: TEST_P7 customers, bookings + their transactions/commissions/payments,
fund requests + their transactions, notifications created during the run;
restores agent booking balance. Run with -n0.
"""
import os
from datetime import date, timedelta
from decimal import Decimal

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("yongmichael992@gmail.com", "Admin@12345")
AGENT = ("agent.demo@biyahetabai.example.com", "Agent@12345")
CEBU = "4c02efb1-1bc8-4a09-8636-0a49020f42f4"  # net 3500 + markup 500 -> retail 4000/pax
OTHER_AGENT = "bab98fb5-08ae-4dce-9e5f-7c36d6121b62"
FUTURE = (date.today() + timedelta(days=40)).isoformat()
TODAY = date.today().isoformat()
PFX = "TEST_P7"


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


@pytest.fixture(scope="module")
def agent_ids(db):
    u = db.users.find_one({"email": AGENT[0]})
    return u["_id"], db.agent_profiles.find_one({"user_id": u["_id"]})["_id"]


@pytest.fixture(scope="module", autouse=True)
def cleanup(db, agent_ids):
    uid, aid = agent_ids
    bal_before = db.agent_profiles.find_one({"_id": aid})["booking_account"]["balance"]
    ex_b = {b["_id"] for b in db.bookings.find({}, {"_id": 1})}
    ex_n = {n["_id"] for n in db.notifications.find({}, {"_id": 1})}
    ex_fr = {f["_id"] for f in db.fund_requests.find({}, {"_id": 1})}
    ex_p = {p["_id"] for p in db.booking_payments.find({}, {"_id": 1})}
    read_state = {n["_id"]: n.get("is_read") for n in db.notifications.find({"user_id": uid})}
    yield
    new_b = [b["_id"] for b in db.bookings.find({"_id": {"$nin": list(ex_b)}}, {"_id": 1})]
    new_fr = [f["_id"] for f in db.fund_requests.find({"_id": {"$nin": list(ex_fr)}}, {"_id": 1})]
    db.financial_transactions.delete_many({"ref_type": "booking", "ref_id": {"$in": new_b}})
    db.financial_transactions.delete_many({"ref_type": "fund_request", "ref_id": {"$in": new_fr}})
    db.commissions.delete_many({"booking_id": {"$in": new_b}})
    db.booking_payments.delete_many({"_id": {"$nin": list(ex_p)}})
    db.bookings.delete_many({"_id": {"$in": new_b}})
    db.fund_requests.delete_many({"_id": {"$in": new_fr}})
    db.notifications.delete_many({"_id": {"$nin": list(ex_n)}})
    for nid, r in read_state.items():
        db.notifications.update_one({"_id": nid}, {"$set": {"is_read": bool(r)}})
    db.customers.delete_many({"first_name": {"$regex": f"^{PFX}"}})
    db.agent_profiles.update_one({"_id": aid}, {"$set": {"booking_account.balance": bal_before}})


@pytest.fixture(scope="module")
def customer(agent):
    r = agent.post(f"{API}/agent/customers", json={"first_name": f"{PFX}_Juan", "last_name": "Cruz"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["customer"]


def _book(agent, customer, pax=2):
    r = agent.post(f"{API}/agent/bookings", json={
        "customer_id": customer["id"], "package_id": CEBU, "pax": pax, "travel_start_date": FUTURE,
        "traveler_names": [f"{PFX} T{i}" for i in range(pax)],
    }, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["booking"]


def _notifs(agent, limit=50):
    r = agent.get(f"{API}/agent/notifications", params={"limit": limit}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _for(agent, ref_id, kind):
    return [n for n in _notifs(agent)["notifications"] if n["ref_id"] == ref_id and n["kind"] == kind]


# --- RBAC ---
class TestRBAC:
    def test_anon_401(self):
        assert requests.get(f"{API}/agent/notifications", timeout=15).status_code == 401

    def test_admin_403(self, admin):
        assert admin.get(f"{API}/agent/notifications", timeout=15).status_code == 403


# --- booking status alerts ---
class TestBookingAlerts:
    def test_confirm_then_complete(self, admin, agent, customer):
        b = _book(agent, customer)
        before = _notifs(agent)["unread_count"]
        r = admin.patch(f"{API}/admin/bookings/{b['id']}/status", json={"status": "confirmed"}, timeout=20)
        assert r.status_code == 200, r.text
        ns = _for(agent, b["id"], "booking.confirmed")
        assert len(ns) == 1
        n = ns[0]
        assert n["title"] == "Booking confirmed" and b["reference_code"] in n["body"]
        assert n["ref_type"] == "booking" and n["is_read"] is False
        assert _notifs(agent)["unread_count"] == before + 1
        r = admin.patch(f"{API}/admin/bookings/{b['id']}/status", json={"status": "completed"}, timeout=20)
        assert r.status_code == 200, r.text
        ns = _for(agent, b["id"], "booking.completed")
        assert len(ns) == 1 and ns[0]["title"] == "Trip completed"

    def test_cancel_with_refund(self, admin, agent, customer):
        b = _book(agent, customer)
        r = admin.patch(f"{API}/admin/bookings/{b['id']}/status",
                        json={"status": "cancelled", "refund": True, "reason": "TEST_P7 weather"}, timeout=20)
        assert r.status_code == 200, r.text
        ns = _for(agent, b["id"], "booking.cancelled")
        assert len(ns) == 1
        assert "₱7,000.00 was refunded" in ns[0]["body"], ns[0]["body"]
        assert "TEST_P7 weather" in ns[0]["body"]

    def test_cancel_without_refund(self, admin, agent, customer):
        b = _book(agent, customer)
        r = admin.patch(f"{API}/admin/bookings/{b['id']}/status", json={"status": "cancelled", "refund": False}, timeout=20)
        assert r.status_code == 200, r.text
        ns = _for(agent, b["id"], "booking.cancelled")
        assert len(ns) == 1 and "No refund was issued" in ns[0]["body"]

    def test_invalid_transition_no_alert(self, admin, agent, customer):
        b = _book(agent, customer)
        r = admin.patch(f"{API}/admin/bookings/{b['id']}/status", json={"status": "completed"}, timeout=20)
        if r.status_code == 400:
            assert _for(agent, b["id"], "booking.completed") == []


# --- fund request alerts ---
class TestFundRequestAlerts:
    def test_approve(self, admin, agent, agent_ids):
        r = admin.post(f"{API}/admin/fund-requests", json={"agent_id": agent_ids[1], "amount": "1234.50",
                                                           "reference_no": f"{PFX}-A"}, timeout=15)
        assert r.status_code == 200, r.text
        fid = r.json()["fund_request"]["id"]
        r = admin.post(f"{API}/admin/fund-requests/{fid}/approve", json={"decision_note": "ok"}, timeout=15)
        assert r.status_code == 200, r.text
        ns = _for(agent, fid, "fund_request.approved")
        assert len(ns) == 1 and "₱1,234.50" in ns[0]["body"] and ns[0]["ref_type"] == "fund_request"

    def test_reject(self, admin, agent, agent_ids):
        r = admin.post(f"{API}/admin/fund-requests", json={"agent_id": agent_ids[1], "amount": "500"}, timeout=15)
        fid = r.json()["fund_request"]["id"]
        r = admin.post(f"{API}/admin/fund-requests/{fid}/reject", json={"decision_note": "TEST_P7 no proof"}, timeout=15)
        assert r.status_code == 200, r.text
        ns = _for(agent, fid, "fund_request.rejected")
        assert len(ns) == 1 and "TEST_P7 no proof" in ns[0]["body"]


# --- read / read-all / isolation ---
class TestReadState:
    def test_mark_one_read(self, agent):
        data = _notifs(agent)
        unread = [n for n in data["notifications"] if not n["is_read"]]
        assert unread
        r = agent.post(f"{API}/agent/notifications/{unread[0]['id']}/read", timeout=15)
        assert r.status_code == 200
        d2 = _notifs(agent)
        assert d2["unread_count"] == data["unread_count"] - 1
        assert next(n for n in d2["notifications"] if n["id"] == unread[0]["id"])["is_read"] is True

    def test_others_notification_404_and_not_listed(self, agent, db):
        other_uid = db.agent_profiles.find_one({"_id": OTHER_AGENT})["user_id"]
        nid = "test-p7-other-notif"
        db.notifications.delete_one({"_id": nid})
        db.notifications.insert_one({"_id": nid, "user_id": other_uid, "kind": "booking.confirmed", "title": "x",
                                     "body": "x", "is_read": False, "created_at": "2099-01-01T00:00:00+00:00"})
        try:
            assert agent.post(f"{API}/agent/notifications/{nid}/read", timeout=15).status_code == 404
            assert nid not in [n["id"] for n in _notifs(agent, 100)["notifications"]]
            assert db.notifications.find_one({"_id": nid})["is_read"] is False
        finally:
            db.notifications.delete_one({"_id": nid})

    def test_read_all(self, agent):
        r = agent.post(f"{API}/agent/notifications/read-all", timeout=15)
        assert r.status_code == 200 and r.json()["ok"] is True
        d = _notifs(agent)
        assert d["unread_count"] == 0 and all(n["is_read"] for n in d["notifications"])

    def test_missing_404(self, agent):
        assert agent.post(f"{API}/agent/notifications/nope/read", timeout=15).status_code == 404


# --- customer payments ---
@pytest.fixture(scope="module")
def pay_booking(agent, customer):
    return _book(agent, customer)  # pending, total retail 8000


class TestPayments:
    def test_initial(self, agent, pay_booking):
        r = agent.get(f"{API}/agent/bookings/{pay_booking['id']}/payments", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["payments"] == [] and d["total_due"] == "8000.00" and d["balance_due"] == "8000.00"
        assert d["guest_payment_status"] == "unpaid"
        assert pay_booking["amount_paid"] == "0.00" and pay_booking["balance_due"] == "8000.00"

    @pytest.mark.parametrize("body,code", [
        ({"amount": "0", "method": "cash", "paid_on": TODAY}, 422),
        ({"amount": "-5", "method": "cash", "paid_on": TODAY}, 422),
        ({"amount": "100", "method": "bitcoin", "paid_on": TODAY}, 422),
        ({"amount": "8000.01", "method": "cash", "paid_on": TODAY}, 400),
        ({"amount": "100", "method": "cash", "paid_on": (date.today() + timedelta(days=5)).isoformat()}, 400),
        ({"amount": "100", "method": "cash", "paid_on": "2026-13-45"}, 400),
    ])
    def test_validation(self, agent, pay_booking, body, code):
        r = agent.post(f"{API}/agent/bookings/{pay_booking['id']}/payments", json=body, timeout=15)
        assert r.status_code == code, r.text

    def test_partial_then_paid_then_delete(self, agent, admin, db, pay_booking):
        bid = pay_booking["id"]
        r = agent.post(f"{API}/agent/bookings/{bid}/payments", json={
            "amount": "3000", "method": "gcash", "paid_on": TODAY, "reference": f"  {PFX}-REF ", "note": "deposit"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["amount_paid"] == "3000.00" and d["balance_due"] == "5000.00" and d["guest_payment_status"] == "partial"
        p1 = d["payments"][0]
        assert p1["reference"] == f"{PFX}-REF" and p1["method"] == "gcash"
        b = agent.get(f"{API}/agent/bookings/{bid}", timeout=15).json()["booking"]
        assert b["guest_payment_status"] == "partial" and b["balance_due"] == "5000.00"
        # overpay check vs remaining
        r = agent.post(f"{API}/agent/bookings/{bid}/payments", json={"amount": "5000.01", "method": "cash", "paid_on": TODAY}, timeout=15)
        assert r.status_code == 400
        # owing filter + dashboard
        owing = agent.get(f"{API}/agent/bookings", params={"payment": "owing"}, timeout=15).json()["bookings"]
        assert bid in [x["id"] for x in owing]
        assert all(x["status"] != "cancelled" and x["guest_payment_status"] != "paid" for x in owing)
        dash = agent.get(f"{API}/agent/dashboard", timeout=15).json()
        assert Decimal(dash["customer_balance_due"]) >= Decimal("5000") and dash["bookings_owing"] >= 1
        # admin sees same
        ad = admin.get(f"{API}/admin/bookings/{bid}", timeout=15).json()["booking"]
        assert ad["guest_payment_status"] == "partial"
        assert Decimal(ad["amount_paid"]) == Decimal("3000") and Decimal(ad["balance_due"]) == Decimal("5000")
        assert len(ad["payments"]) == 1 and ad["payments"][0]["method"] == "gcash"
        # pay remaining
        r = agent.post(f"{API}/agent/bookings/{bid}/payments", json={"amount": "5000", "method": "bank_transfer", "paid_on": TODAY}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["guest_payment_status"] == "paid" and d["balance_due"] == "0.00" and len(d["payments"]) == 2
        owing = agent.get(f"{API}/agent/bookings", params={"payment": "owing"}, timeout=15).json()["bookings"]
        assert bid not in [x["id"] for x in owing]
        r = agent.post(f"{API}/agent/bookings/{bid}/payments", json={"amount": "1", "method": "cash", "paid_on": TODAY}, timeout=15)
        assert r.status_code == 400
        # delete -> back to partial
        r = agent.delete(f"{API}/agent/bookings/{bid}/payments/{p1['id']}", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["guest_payment_status"] == "partial" and r.json()["balance_due"] == "3000.00"
        assert db.bookings.find_one({"_id": bid})["guest_payment_status"] == "partial"
        assert agent.delete(f"{API}/agent/bookings/{bid}/payments/{p1['id']}", timeout=15).status_code == 404
        # audit
        acts = [a["action"] for a in db.audit_logs.find({"target_id": bid})]
        assert "booking.payment.add" in acts and "booking.payment.delete" in acts
        # delete last -> unpaid
        rest = r.json()["payments"][0]["id"]
        r = agent.delete(f"{API}/agent/bookings/{bid}/payments/{rest}", timeout=15)
        assert r.json()["guest_payment_status"] == "unpaid"
        assert db.bookings.find_one({"_id": bid})["guest_payment_status"] == "unpaid"

    def test_cancelled_booking_rejected(self, agent, admin, customer):
        b = _book(agent, customer)
        admin.patch(f"{API}/admin/bookings/{b['id']}/status", json={"status": "cancelled", "refund": True}, timeout=20)
        r = agent.post(f"{API}/agent/bookings/{b['id']}/payments", json={"amount": "100", "method": "cash", "paid_on": TODAY}, timeout=15)
        assert r.status_code == 400 and "cancelled" in r.text.lower()
        owing = agent.get(f"{API}/agent/bookings", params={"payment": "owing"}, timeout=15).json()["bookings"]
        assert b["id"] not in [x["id"] for x in owing]

    def test_other_agent_booking_404(self, agent, db):
        bid = "test-p7-other-booking"
        db.bookings.delete_one({"_id": bid})
        db.bookings.insert_one({"_id": bid, "agent_id": OTHER_AGENT, "status": "confirmed", "package_id": CEBU,
                                "customer_id": "x", "pax": 1, "created_at": "2026-01-01T00:00:00+00:00"})
        try:
            assert agent.get(f"{API}/agent/bookings/{bid}/payments", timeout=15).status_code == 404
            r = agent.post(f"{API}/agent/bookings/{bid}/payments", json={"amount": "1", "method": "cash", "paid_on": TODAY}, timeout=15)
            assert r.status_code == 404
            assert agent.delete(f"{API}/agent/bookings/{bid}/payments/x", timeout=15).status_code == 404
        finally:
            db.bookings.delete_one({"_id": bid})

    def test_list_has_payment_fields(self, agent):
        rows = agent.get(f"{API}/agent/bookings", timeout=15).json()["bookings"]
        assert rows and all("amount_paid" in x and "balance_due" in x for x in rows)

    def test_owing_bad_value_422(self, agent):
        assert agent.get(f"{API}/agent/bookings", params={"payment": "paid"}, timeout=15).status_code == 422

    def test_admin_override_409(self, admin, pay_booking):
        r = admin.patch(f"{API}/admin/bookings/{pay_booking['id']}/guest-payment-status",
                        json={"status": "paid"}, timeout=15)
        assert r.status_code == 409
