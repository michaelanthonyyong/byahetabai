"""Phase 9 — agent brand colour on PDFs + private expiring share links.

Restores the demo agent's brand_color / balance, cleans TEST_P9 customers,
bookings, payments and share links it creates. Run with -n0.
"""
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pymupdf
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("yongmichael992@gmail.com", "Admin@12345")
AGENT = ("agent.demo@biyahetabai.example.com", "Agent@12345")
CEBU = "4c02efb1-1bc8-4a09-8636-0a49020f42f4"
OTHER_AGENT = "bab98fb5-08ae-4dce-9e5f-7c36d6121b62"
PFX = "TEST_P9"
TODAY = date.today()


def d(n):
    return (TODAY + timedelta(days=n)).isoformat()


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return s


def _fills(content):
    """Set of rounded RGB fill colours drawn in the PDF."""
    doc = pymupdf.open(stream=content, filetype="pdf")
    out = set()
    for p in doc:
        for dr in p.get_drawings():
            for k in ("fill", "color"):
                c = dr.get(k)
                if c:
                    out.add(tuple(round(x * 255) for x in c))
    return out


def _text(content):
    return "\n".join(p.get_text() for p in pymupdf.open(stream=content, filetype="pdf"))


BROWN = (0x7C, 0x2D, 0x12)
TEAL = (0x11, 0x5E, 0x59)


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
    prof = db.agent_profiles.find_one({"_id": aid})
    saved_color = prof.get("brand_color")
    bal = prof["booking_account"]["balance"]
    ex_b = {b["_id"] for b in db.bookings.find({}, {"_id": 1})}
    ex_n = {n["_id"] for n in db.notifications.find({}, {"_id": 1})}
    ex_p = {p["_id"] for p in db.booking_payments.find({}, {"_id": 1})}
    ex_l = {x["_id"] for x in db.share_links.find({}, {"_id": 1})}
    yield
    new_b = [b["_id"] for b in db.bookings.find({"_id": {"$nin": list(ex_b)}}, {"_id": 1})]
    db.financial_transactions.delete_many({"ref_type": "booking", "ref_id": {"$in": new_b}})
    db.commissions.delete_many({"booking_id": {"$in": new_b}})
    db.booking_payments.delete_many({"_id": {"$nin": list(ex_p)}})
    db.bookings.delete_many({"_id": {"$in": new_b}})
    db.notifications.delete_many({"_id": {"$nin": list(ex_n)}})
    db.share_links.delete_many({"_id": {"$nin": list(ex_l)}})
    db.customers.delete_many({"first_name": {"$regex": f"^{PFX}"}})
    db.agent_profiles.update_one({"_id": aid}, {"$set": {"brand_color": saved_color, "booking_account.balance": bal, "status": "active"}})
    db.users.update_one({"email": AGENT[0]}, {"$set": {"status": "active"}})


@pytest.fixture(scope="module")
def booking(agent):
    r = agent.post(f"{API}/agent/customers", json={"first_name": f"{PFX}_Ana", "last_name": "Cruz"}, timeout=15)
    assert r.status_code == 200, r.text
    c = r.json()["customer"]
    r = agent.post(f"{API}/agent/bookings", json={
        "customer_id": c["id"], "package_id": CEBU, "pax": 1, "travel_start_date": d(20),
        "traveler_names": [f"{PFX} T0"]}, timeout=20)
    assert r.status_code == 200, r.text
    b = r.json()["booking"]
    r = agent.post(f"{API}/agent/bookings/{b['id']}/payments",
                   json={"amount": "1500", "method": "gcash", "paid_on": d(0), "reference": "P9REF"}, timeout=15)
    assert r.status_code == 200, r.text
    return b, r.json()["payments"][-1]


def _share(agent, **body):
    return agent.post(f"{API}/agent/share-links", json=body, timeout=30)


# --- brand colour on profile ---
class TestBrandColor:
    def test_set_invalid_reset(self, agent):
        r = agent.patch(f"{API}/agent/profile", json={"brand_color": "#7c2d12"}, timeout=15)
        assert r.status_code == 200 and r.json()["profile"]["brand_color"] == "#7c2d12"
        assert agent.get(f"{API}/agent/profile", timeout=15).json()["profile"]["brand_color"] == "#7c2d12"
        for bad in ("red", "#abc", "7c2d12", "#7c2d1z", "#7c2d123"):
            assert agent.patch(f"{API}/agent/profile", json={"brand_color": bad}, timeout=15).status_code == 422, bad
        r = agent.patch(f"{API}/agent/profile", json={"brand_color": ""}, timeout=15)
        assert r.status_code == 200 and r.json()["profile"]["brand_color"] is None

    def test_pdfs_use_colour(self, agent, booking):
        b, p = booking
        agent.patch(f"{API}/agent/profile", json={"brand_color": "#7c2d12"}, timeout=15)
        urls = [("post", f"{API}/agent/quotes/pdf", {"package_id": CEBU, "pax": 2}),
                ("get", f"{API}/agent/bookings/{b['id']}/quote.pdf", None),
                ("get", f"{API}/agent/bookings/{b['id']}/payments/{p['id']}/receipt.pdf", None)]
        for m, u, j in urls:
            r = getattr(agent, m)(u, json=j, timeout=60) if j else getattr(agent, m)(u, timeout=60)
            assert r.status_code == 200, (u, r.text)
            f = _fills(r.content)
            assert BROWN in f and TEAL not in f, (u, f)
        agent.patch(f"{API}/agent/profile", json={"brand_color": ""}, timeout=15)
        for m, u, j in urls:
            r = getattr(agent, m)(u, json=j, timeout=60) if j else getattr(agent, m)(u, timeout=60)
            f = _fills(r.content)
            assert TEAL in f and BROWN not in f, (u, f)

    def test_receipt_still_attachment(self, agent, booking):
        b, p = booking
        r = agent.get(f"{API}/agent/bookings/{b['id']}/payments/{p['id']}/receipt.pdf", timeout=60)
        assert r.headers["content-type"] == "application/pdf" and r.headers["content-disposition"].startswith("attachment")


# --- share links ---
class TestShareLinks:
    def test_quote_link(self, agent, db, aid):
        r = _share(agent, kind="quote", package_id=CEBU, pax=2, customer_name=f"{PFX} Cust", travel_date=d(30))
        assert r.status_code == 200, r.text
        L = r.json()["link"]
        assert L["kind"] == "quote" and L["status"] == "active" and L["open_count"] == 0
        assert L["path"].startswith("/api/share/") and f"{PFX} Cust" in L["label"]
        exp = datetime.fromisoformat(L["expires_at"]) - datetime.fromisoformat(L["created_at"])
        assert exp == timedelta(days=30)
        row = db.share_links.find_one({"_id": L["id"]})
        assert row["agent_id"] == aid and row["params"]["unit_retail"] == "4000.00"
        assert db.audit_logs.find_one({"action": "share_link.create", "target_id": L["id"]})
        # public open, no auth
        g = requests.get(f"{BASE_URL}{L['path']}", timeout=60)
        assert g.status_code == 200 and g.headers["content-type"] == "application/pdf"
        assert g.headers["content-disposition"].startswith("inline")
        assert "no-store" in g.headers.get("cache-control", "")
        t = _text(g.content)
        assert "PHP 8,000.00" in t and f"{PFX} Cust" in t
        requests.get(f"{BASE_URL}{L['path']}", timeout=60)
        row = db.share_links.find_one({"_id": L["id"]})
        assert row["open_count"] == 2 and row["last_opened_at"]
        # snapshot price: markup change doesn't change shared quote
        m = db.agent_package_markups.find_one({"agent_id": aid, "package_id": CEBU})
        db.agent_package_markups.update_one({"_id": m["_id"]}, {"$set": {"markup_amount": "600"}})
        try:
            assert "PHP 8,000.00" in _text(requests.get(f"{BASE_URL}{L['path']}", timeout=60).content)
        finally:
            db.agent_package_markups.update_one({"_id": m["_id"]}, {"$set": {"markup_amount": m["markup_amount"]}})

    def test_quote_validation(self, agent, db, aid):
        assert _share(agent, kind="quote", pax=2).status_code == 400
        assert _share(agent, kind="quote", package_id=CEBU).status_code == 400
        assert _share(agent, kind="quote", package_id=str(uuid.uuid4()), pax=1).status_code == 404
        assert _share(agent, kind="bogus", booking_id="x").status_code == 422
        assert _share(agent, kind="quote", package_id=CEBU, pax=2, travel_date=d(-3)).status_code == 400
        m = db.agent_package_markups.find_one({"agent_id": aid, "package_id": CEBU})
        db.agent_package_markups.delete_one({"_id": m["_id"]})
        try:
            r = _share(agent, kind="quote", package_id=CEBU, pax=2)
            assert r.status_code == 400 and "markup" in r.text.lower()
        finally:
            db.agent_package_markups.insert_one(m)

    def test_booking_quote_and_receipt(self, agent, booking):
        b, p = booking
        r = _share(agent, kind="booking_quote", booking_id=b["id"])
        assert r.status_code == 200 and b["reference_code"] in r.json()["link"]["label"]
        g = requests.get(f"{BASE_URL}{r.json()['link']['path']}", timeout=60)
        assert g.status_code == 200 and g.headers["content-disposition"].startswith("inline")
        assert b["reference_code"] in _text(g.content)
        r = _share(agent, kind="receipt", booking_id=b["id"], payment_id=p["id"])
        assert r.status_code == 200, r.text
        assert f"{b['reference_code']}-R" in r.json()["link"]["label"]
        g = requests.get(f"{BASE_URL}{r.json()['link']['path']}", timeout=60)
        assert g.status_code == 200 and "P9REF" in _text(g.content)
        assert "receipt-" in g.headers["content-disposition"]
        assert _share(agent, kind="receipt", booking_id=b["id"]).status_code == 400
        assert _share(agent, kind="booking_quote").status_code == 400
        assert _share(agent, kind="receipt", booking_id=b["id"], payment_id=str(uuid.uuid4())).status_code == 404

    def test_other_agent_404(self, agent, db):
        bid, pid = str(uuid.uuid4()), str(uuid.uuid4())
        db.bookings.insert_one({"_id": bid, "agent_id": OTHER_AGENT, "reference_code": "TEST_P9-X", "package_id": CEBU,
                                "customer_id": "x", "pax": 1, "status": "pending"})
        db.booking_payments.insert_one({"_id": pid, "booking_id": bid, "agent_id": OTHER_AGENT, "amount": "100",
                                        "method": "cash", "paid_on": d(0)})
        try:
            assert _share(agent, kind="booking_quote", booking_id=bid).status_code == 404
            assert _share(agent, kind="receipt", booking_id=bid, payment_id=pid).status_code == 404
        finally:
            db.bookings.delete_one({"_id": bid})
            db.booking_payments.delete_one({"_id": pid})

    def test_unauth_and_admin(self, admin):
        assert requests.post(f"{API}/agent/share-links", json={"kind": "booking_quote", "booking_id": "x"}, timeout=15).status_code == 401
        assert admin.get(f"{API}/agent/share-links", timeout=15).status_code == 403

    def test_list_and_revoke(self, agent, db):
        L = _share(agent, kind="quote", package_id=CEBU, pax=1).json()["link"]
        other = {"_id": uuid.uuid4().hex, "token": uuid.uuid4().hex, "agent_id": OTHER_AGENT, "kind": "quote",
                 "label": "TEST_P9 other", "params": {}, "expires_at": d(10), "revoked_at": None,
                 "open_count": 0, "created_at": d(0), "updated_at": d(0)}
        db.share_links.insert_one(other)
        try:
            ids = [x["id"] for x in agent.get(f"{API}/agent/share-links", timeout=15).json()["links"]]
            assert L["id"] in ids and other["_id"] not in ids
            assert agent.post(f"{API}/agent/share-links/{other['_id']}/revoke", timeout=15).status_code == 404
            assert agent.post(f"{API}/agent/share-links/{uuid.uuid4().hex}/revoke", timeout=15).status_code == 404
        finally:
            db.share_links.delete_one({"_id": other["_id"]})
        r = agent.post(f"{API}/agent/share-links/{L['id']}/revoke", timeout=15)
        assert r.status_code == 200 and r.json()["link"]["status"] == "revoked"
        assert agent.post(f"{API}/agent/share-links/{L['id']}/revoke", timeout=15).json()["link"]["status"] == "revoked"
        assert db.audit_logs.count_documents({"action": "share_link.revoke", "target_id": L["id"]}) == 1
        g = requests.get(f"{BASE_URL}{L['path']}", timeout=30)
        assert g.status_code == 410 and "text/html" in g.headers["content-type"]
        lst = {x["id"]: x for x in agent.get(f"{API}/agent/share-links", timeout=15).json()["links"]}
        assert lst[L["id"]]["status"] == "revoked"

    def test_unknown_and_expired(self, agent, db):
        g = requests.get(f"{API}/share/doesnotexist123", timeout=15)
        assert g.status_code == 404 and "text/html" in g.headers["content-type"]
        L = _share(agent, kind="quote", package_id=CEBU, pax=1).json()["link"]
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        db.share_links.update_one({"_id": L["id"]}, {"$set": {"expires_at": past}})
        assert requests.get(f"{BASE_URL}{L['path']}", timeout=30).status_code == 410
        lst = {x["id"]: x for x in agent.get(f"{API}/agent/share-links", timeout=15).json()["links"]}
        assert lst[L["id"]]["status"] == "expired"

    def test_deleted_payment_410(self, agent, booking):
        b, _ = booking
        r = agent.post(f"{API}/agent/bookings/{b['id']}/payments",
                       json={"amount": "100", "method": "cash", "paid_on": d(0)}, timeout=15)
        p2 = r.json()["payments"][-1]
        L = _share(agent, kind="receipt", booking_id=b["id"], payment_id=p2["id"]).json()["link"]
        assert requests.get(f"{BASE_URL}{L['path']}", timeout=60).status_code == 200
        assert agent.delete(f"{API}/agent/bookings/{b['id']}/payments/{p2['id']}", timeout=15).status_code == 200
        g = requests.get(f"{BASE_URL}{L['path']}", timeout=30)
        assert g.status_code == 410 and "text/html" in g.headers["content-type"]

    def test_disabled_agent_410(self, agent, admin, aid):
        L = _share(agent, kind="quote", package_id=CEBU, pax=1).json()["link"]
        assert admin.patch(f"{API}/admin/agents/{aid}/status", json={"status": "disabled"}, timeout=15).status_code == 200
        try:
            assert requests.get(f"{BASE_URL}{L['path']}", timeout=30).status_code == 410
        finally:
            assert admin.patch(f"{API}/admin/agents/{aid}/status", json={"status": "active"}, timeout=15).status_code == 200
        assert requests.get(f"{BASE_URL}{L['path']}", timeout=60).status_code == 200

    def test_shared_pdf_uses_brand_colour(self, agent):
        agent.patch(f"{API}/agent/profile", json={"brand_color": "#7c2d12"}, timeout=15)
        L = _share(agent, kind="quote", package_id=CEBU, pax=1).json()["link"]
        assert BROWN in _fills(requests.get(f"{BASE_URL}{L['path']}", timeout=60).content)
