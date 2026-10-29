"""Phase 8 — Agent branding (business name + logo), payment receipt PDFs,
agent-branded quotes, and trip-due reminders.

Restores the demo agent's business_name/logo fields, cleans up TEST_P8 data,
notifications, audit rows are left (append-only). Run with -n0.
"""
import io
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pymupdf
import pytest
import requests
from dotenv import load_dotenv
from PIL import Image
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("yongmichael992@gmail.com", "Admin@12345")
AGENT = ("agent.demo@biyahetabai.example.com", "Agent@12345")
CEBU = "4c02efb1-1bc8-4a09-8636-0a49020f42f4"  # retail 4000/pax for demo agent
OTHER_AGENT = "bab98fb5-08ae-4dce-9e5f-7c36d6121b62"
PFX = "TEST_P8"
BRAND = "TEST_P8 Sunrise Tours"
TODAY = date.today()


def d(n):
    return (TODAY + timedelta(days=n)).isoformat()


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return s


def _png(color=(200, 30, 30), size=(120, 60)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


def _jpg():
    b = io.BytesIO()
    Image.new("RGB", (80, 80), (10, 120, 200)).save(b, "JPEG")
    return b.getvalue()


def _pdf_text(content):
    doc = pymupdf.open(stream=content, filetype="pdf")
    # the demo agent's email domain is biyahetabai.example.com; strip it before brand checks
    text = "\n".join(p.get_text() for p in doc).replace(AGENT[0], "<agent-email>")
    return text, sum(len(p.get_images()) for p in doc)


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
def aid(db):
    u = db.users.find_one({"email": AGENT[0]})
    return db.agent_profiles.find_one({"user_id": u["_id"]})["_id"]


@pytest.fixture(scope="module", autouse=True)
def cleanup(db, aid):
    keys = ["business_name", "logo_path", "logo_content_type", "logo_updated_at"]
    prof = db.agent_profiles.find_one({"_id": aid})
    saved = {k: prof.get(k) for k in keys}
    bal = prof["booking_account"]["balance"]
    ex_b = {b["_id"] for b in db.bookings.find({}, {"_id": 1})}
    ex_n = {n["_id"] for n in db.notifications.find({}, {"_id": 1})}
    ex_p = {p["_id"] for p in db.booking_payments.find({}, {"_id": 1})}
    yield
    new_b = [b["_id"] for b in db.bookings.find({"_id": {"$nin": list(ex_b)}}, {"_id": 1})]
    db.financial_transactions.delete_many({"ref_type": "booking", "ref_id": {"$in": new_b}})
    db.commissions.delete_many({"booking_id": {"$in": new_b}})
    db.booking_payments.delete_many({"_id": {"$nin": list(ex_p)}})
    db.bookings.delete_many({"_id": {"$in": new_b}})
    db.notifications.delete_many({"_id": {"$nin": list(ex_n)}})
    db.customers.delete_many({"first_name": {"$regex": f"^{PFX}"}})
    db.agent_profiles.update_one({"_id": aid}, {"$set": {**saved, "booking_account.balance": bal}})


@pytest.fixture(scope="module")
def customer(agent):
    r = agent.post(f"{API}/agent/customers", json={"first_name": f"{PFX}_Maria", "last_name": "Reyes"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["customer"]


def _book(agent, customer, days=5, pax=1):
    r = agent.post(f"{API}/agent/bookings", json={
        "customer_id": customer["id"], "package_id": CEBU, "pax": pax, "travel_start_date": d(days),
        "traveler_names": [f"{PFX} T{i}" for i in range(pax)],
    }, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["booking"]


def _pay(agent, bid, amount, method="cash", ref=None):
    r = agent.post(f"{API}/agent/bookings/{bid}/payments",
                   json={"amount": str(amount), "method": method, "paid_on": d(0), "reference": ref}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# --- profile / business name ---
class TestBusinessName:
    def test_profile_fields(self, agent):
        p = agent.get(f"{API}/agent/profile", timeout=15).json()["profile"]
        for k in ("business_name", "brand_name", "has_logo", "logo_updated_at", "agency_name"):
            assert k in p

    def test_set_and_fallback(self, agent, admin, db, aid):
        r = agent.patch(f"{API}/agent/profile", json={"business_name": f"  {BRAND}  "}, timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()["profile"]
        assert p["business_name"] == BRAND and p["brand_name"] == BRAND
        assert agent.get(f"{API}/agent/profile", timeout=15).json()["profile"]["brand_name"] == BRAND
        assert db.agent_profiles.find_one({"_id": aid})["agency_name"] == "Demo Travel Agency"
        r = agent.patch(f"{API}/agent/profile", json={"business_name": "   "}, timeout=15)
        p = r.json()["profile"]
        assert p["business_name"] is None and p["brand_name"] == p["agency_name"] == "Demo Travel Agency"
        agent.patch(f"{API}/agent/profile", json={"business_name": BRAND}, timeout=15)

    def test_max_length(self, agent):
        assert agent.patch(f"{API}/agent/profile", json={"business_name": "x" * 121}, timeout=15).status_code == 422
        assert agent.patch(f"{API}/agent/profile", json={"business_name": "x" * 120}, timeout=15).status_code == 200
        agent.patch(f"{API}/agent/profile", json={"business_name": BRAND}, timeout=15)

    def test_admin_cannot_access(self, admin):
        assert admin.get(f"{API}/agent/profile/logo", timeout=15).status_code == 403
        assert requests.post(f"{API}/agent/profile/logo", files={"file": ("a.png", _png(), "image/png")}, timeout=15).status_code == 401


# --- logo upload ---
class TestLogo:
    def test_reject_non_images(self, agent):
        for name, data, ct in [
            ("a.txt", b"hello world", "text/plain"),
            ("fake.png", b"\x89PNG\r\n\x1a\nnotreallyapng" * 10, "image/png"),
            ("a.gif", b"GIF89a" + b"\x00" * 50, "image/gif"),
        ]:
            r = agent.post(f"{API}/agent/profile/logo", files={"file": (name, data, ct)}, timeout=30)
            assert r.status_code == 400, (name, r.status_code, r.text)

    def test_reject_gif_real(self, agent):
        b = io.BytesIO()
        Image.new("RGB", (10, 10)).save(b, "GIF")
        r = agent.post(f"{API}/agent/profile/logo", files={"file": ("a.gif", b.getvalue(), "image/gif")}, timeout=30)
        assert r.status_code == 400

    def test_reject_over_2mb(self, agent):
        data = _png() + b"\x00" * (2 * 1024 * 1024)
        r = agent.post(f"{API}/agent/profile/logo", files={"file": ("big.png", data, "image/png")}, timeout=60)
        assert r.status_code == 400 and "2 MB" in r.text

    def test_upload_png_get_remove(self, agent, db, aid):
        png = _png()
        r = agent.post(f"{API}/agent/profile/logo", files={"file": ("logo.png", png, "image/png")}, timeout=60)
        assert r.status_code == 200, r.text
        p = r.json()["profile"]
        assert p["has_logo"] is True and p["logo_updated_at"]
        g = agent.get(f"{API}/agent/profile/logo", timeout=30)
        assert g.status_code == 200 and g.headers["content-type"].startswith("image/png") and g.content == png
        assert db.audit_logs.find_one({"action": "agent.logo.upload", "target_id": aid}, sort=[("created_at", -1)])
        r = agent.delete(f"{API}/agent/profile/logo", timeout=15)
        assert r.status_code == 200 and r.json()["profile"]["has_logo"] is False
        assert agent.get(f"{API}/agent/profile/logo", timeout=15).status_code == 404
        assert agent.get(f"{API}/agent/profile", timeout=15).json()["profile"]["has_logo"] is False
        assert db.audit_logs.find_one({"action": "agent.logo.remove", "target_id": aid})

    def test_upload_jpg(self, agent):
        jpg = _jpg()
        r = agent.post(f"{API}/agent/profile/logo", files={"file": ("logo.jpg", jpg, "image/jpeg")}, timeout=60)
        assert r.status_code == 200, r.text
        g = agent.get(f"{API}/agent/profile/logo", timeout=30)
        assert g.headers["content-type"].startswith("image/jpeg") and g.content == jpg


# --- receipts ---
class TestReceipts:
    @pytest.fixture(scope="class")
    def booking(self, agent, customer):
        agent.patch(f"{API}/agent/profile", json={"business_name": BRAND}, timeout=15)
        r = agent.post(f"{API}/agent/profile/logo", files={"file": ("logo.png", _png(), "image/png")}, timeout=60)
        assert r.status_code == 200
        b = _book(agent, customer, days=6, pax=2)
        p1 = _pay(agent, b["id"], 3000, "gcash", "GC-REF-111")["payments"][-1]
        p2 = _pay(agent, b["id"], 2000, "cash")["payments"][-1]
        return b, p1, p2

    def _receipt(self, agent, bid, pid):
        r = agent.get(f"{API}/agent/bookings/{bid}/payments/{pid}/receipt.pdf", timeout=60)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert "attachment" in r.headers.get("content-disposition", "")
        return r

    def test_first_receipt(self, agent, booking):
        b, p1, _ = booking
        r = self._receipt(agent, b["id"], p1["id"])
        assert f"receipt-{b['reference_code']}-R1.pdf" in r.headers["content-disposition"]
        text, imgs = _pdf_text(r.content)
        assert BRAND in text and f"{b['reference_code']}-R1" in text
        assert "GCash" in text and "GC-REF-111" in text and "PHP 3,000.00" in text
        assert "PHP 8,000.00" in text and "Balance due" in text and "PHP 5,000.00" in text
        assert "PHP 2,000.00" not in text  # second payment not in history yet
        assert f"{PFX}_Maria Reyes" in text
        assert imgs >= 1
        low = text.lower()
        assert "biyahe" not in low and "markup" not in low and "net cost" not in low
        assert "7,000.00" not in text  # net cost 3500*2

    def test_second_receipt(self, agent, booking):
        b, p1, p2 = booking
        text, _ = _pdf_text(self._receipt(agent, b["id"], p2["id"]).content)
        assert f"{b['reference_code']}-R2" in text
        assert "PHP 2,000.00" in text and "PHP 3,000.00" in text  # both in history; balance 3000
        assert "Balance due" in text and "Biyahe" not in text

    def test_fully_paid_receipt_no_logo(self, agent, booking):
        b, _, _ = booking
        p3 = _pay(agent, b["id"], 3000, "bank_transfer")["payments"][-1]
        agent.delete(f"{API}/agent/profile/logo", timeout=15)
        text, imgs = _pdf_text(self._receipt(agent, b["id"], p3["id"]).content)
        assert f"{b['reference_code']}-R3" in text and "Fully paid" in text and "Balance due" not in text
        assert "Bank transfer" in text and imgs == 0

    def test_unknown_payment_404(self, agent, booking):
        b, _, _ = booking
        assert agent.get(f"{API}/agent/bookings/{b['id']}/payments/{uuid.uuid4()}/receipt.pdf", timeout=15).status_code == 404

    def test_payment_from_other_booking_404(self, agent, customer, booking):
        b, p1, _ = booking
        b2 = _book(agent, customer, days=30)
        assert agent.get(f"{API}/agent/bookings/{b2['id']}/payments/{p1['id']}/receipt.pdf", timeout=15).status_code == 404

    def test_other_agent_booking_404(self, agent, db):
        bid, pid = str(uuid.uuid4()), str(uuid.uuid4())
        db.bookings.insert_one({"_id": bid, "agent_id": OTHER_AGENT, "reference_code": "TEST_P8-X", "package_id": CEBU,
                                "customer_id": "x", "pax": 1, "status": "pending"})
        db.booking_payments.insert_one({"_id": pid, "booking_id": bid, "agent_id": OTHER_AGENT, "amount": "100",
                                        "method": "cash", "paid_on": d(0)})
        try:
            assert agent.get(f"{API}/agent/bookings/{bid}/payments/{pid}/receipt.pdf", timeout=15).status_code == 404
        finally:
            db.bookings.delete_one({"_id": bid})
            db.booking_payments.delete_one({"_id": pid})

    def test_admin_forbidden(self, admin, booking):
        b, p1, _ = booking
        assert admin.get(f"{API}/agent/bookings/{b['id']}/payments/{p1['id']}/receipt.pdf", timeout=15).status_code == 403


# --- quotes use agent branding ---
class TestQuoteBranding:
    def test_quote_pdf(self, agent):
        agent.patch(f"{API}/agent/profile", json={"business_name": BRAND}, timeout=15)
        r = agent.post(f"{API}/agent/quotes/pdf", json={"package_id": CEBU, "pax": 2, "customer_name": "TEST_P8 Q"}, timeout=60)
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
        text, _ = _pdf_text(r.content)
        assert BRAND in text and "biyahe" not in text.lower() and "PHP 8,000.00" in text

    def test_booking_quote_pdf(self, agent, customer):
        b = _book(agent, customer, days=40)
        r = agent.get(f"{API}/agent/bookings/{b['id']}/quote.pdf", timeout=60)
        assert r.status_code == 200
        text, _ = _pdf_text(r.content)
        assert BRAND in text and b["reference_code"] in text and "biyahe" not in text.lower()

    def test_fallback_agency_name(self, agent):
        agent.patch(f"{API}/agent/profile", json={"business_name": ""}, timeout=15)
        r = agent.post(f"{API}/agent/quotes/pdf", json={"package_id": CEBU, "pax": 1}, timeout=60)
        text, _ = _pdf_text(r.content)
        assert "Demo Travel Agency" in text and "biyahe" not in text.lower()
        agent.patch(f"{API}/agent/profile", json={"business_name": BRAND}, timeout=15)


# --- trip due reminders ---
class TestTripsDue:
    @pytest.fixture(scope="class")
    def setup(self, agent, customer, db):
        inside = _book(agent, customer, days=3)
        edge = _book(agent, customer, days=14)
        today_b = _book(agent, customer, days=0)
        far = _book(agent, customer, days=15)
        paid = _book(agent, customer, days=4, pax=1)
        _pay(agent, paid["id"], 4000)
        cancelled = _book(agent, customer, days=5)
        db.bookings.update_one({"_id": cancelled["id"]}, {"$set": {"status": "cancelled"}})
        past = _book(agent, customer, days=10)
        db.bookings.update_one({"_id": past["id"]}, {"$set": {"travel_start_date": d(-1)}})
        partial = _book(agent, customer, days=7)
        _pay(agent, partial["id"], 1000)
        return dict(inside=inside, edge=edge, today=today_b, far=far, paid=paid, cancelled=cancelled, past=past, partial=partial)

    def test_dashboard_list(self, agent, setup):
        r = agent.get(f"{API}/agent/dashboard", timeout=20)
        assert r.status_code == 200
        trips = {t["booking_id"]: t for t in r.json()["trips_due"]}
        for k in ("inside", "edge", "today", "partial"):
            assert setup[k]["id"] in trips, k
        for k in ("far", "paid", "cancelled", "past"):
            assert setup[k]["id"] not in trips, k
        t = trips[setup["partial"]["id"]]
        assert t["balance_due"] == "3000.00" and t["days_left"] == 7
        assert t["customer_name"] == f"{PFX}_Maria Reyes" and t["reference_code"] == setup["partial"]["reference_code"]
        assert trips[setup["edge"]["id"]]["days_left"] == 14 and trips[setup["today"]["id"]]["days_left"] == 0
        dates = [x["travel_start_date"] for x in r.json()["trips_due"]]
        assert dates == sorted(dates)

    def test_one_alert_per_booking(self, agent, db, setup):
        for _ in range(2):
            agent.get(f"{API}/agent/dashboard", timeout=20)
            agent.get(f"{API}/agent/notifications", timeout=20)
        for k in ("inside", "edge", "today", "partial"):
            assert db.notifications.count_documents({"ref_id": setup[k]["id"], "kind": "booking.payment_due"}) == 1, k
        for k in ("far", "paid", "cancelled", "past"):
            assert db.notifications.count_documents({"ref_id": setup[k]["id"], "kind": "booking.payment_due"}) == 0, k
        n = db.notifications.find_one({"ref_id": setup["today"]["id"], "kind": "booking.payment_due"})
        assert "travels today" in n["body"] and n["ref_type"] == "booking"
        n = db.notifications.find_one({"ref_id": setup["partial"]["id"], "kind": "booking.payment_due"})
        assert "in 7 days" in n["body"] and "₱3,000.00" in n["body"]

    def test_concurrent_calls_no_duplicates(self, agent, customer, db):
        b = _book(agent, customer, days=2)

        def hit(i):
            return agent.get(f"{API}/agent/{'dashboard' if i % 2 else 'notifications'}", timeout=30).status_code

        with ThreadPoolExecutor(6) as ex:
            codes = list(ex.map(hit, range(6)))
        assert all(c == 200 for c in codes)
        cnt = db.notifications.count_documents({"ref_id": b["id"], "kind": "booking.payment_due"})
        assert cnt == 1, f"duplicate payment_due notifications under concurrent load: {cnt}"
