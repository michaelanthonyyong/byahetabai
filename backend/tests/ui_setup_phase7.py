"""Setup/cleanup helper for phase 7 UI testing. Usage: python ui_setup_phase7.py setup|cleanup"""
import json, os, sys
from datetime import date, timedelta
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0]
API = f"{BASE}/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
STATE = "/tmp/p7_ui_state.json"
AID = "5bb0fae2-36e9-447c-a731-e917779f6e4c"


def login(e, p):
    s = requests.Session(); s.post(f"{API}/auth/login", json={"email": e, "password": p}).raise_for_status(); return s


if sys.argv[1] == "setup":
    st = {"bal": str(db.agent_profiles.find_one({"_id": AID})["booking_account"]["balance"]),
          "notifs": [n["_id"] for n in db.notifications.find({}, {"_id": 1})],
          "read": {n["_id"]: n.get("is_read") for n in db.notifications.find()},
          "payments": [p["_id"] for p in db.booking_payments.find({}, {"_id": 1})],
          "bookings": [b["_id"] for b in db.bookings.find({}, {"_id": 1})]}
    ag = login("agent.demo@biyahetabai.example.com", "Agent@12345")
    ad = login("yongmichael992@gmail.com", "Admin@12345")
    c = ag.post(f"{API}/agent/customers", json={"first_name": "TEST_P7UI", "last_name": "Buyer"}).json()["customer"]
    b = ag.post(f"{API}/agent/bookings", json={"customer_id": c["id"], "package_id": "4c02efb1-1bc8-4a09-8636-0a49020f42f4",
                "pax": 2, "travel_start_date": (date.today() + timedelta(days=50)).isoformat(),
                "traveler_names": ["TEST A", "TEST B"]}).json()["booking"]
    ad.patch(f"{API}/admin/bookings/{b['id']}/status", json={"status": "confirmed"}).raise_for_status()
    b2 = ag.post(f"{API}/agent/bookings", json={"customer_id": c["id"], "package_id": "4c02efb1-1bc8-4a09-8636-0a49020f42f4",
                 "pax": 1, "travel_start_date": (date.today() + timedelta(days=50)).isoformat(), "traveler_names": ["TEST C"]}).json()["booking"]
    ad.patch(f"{API}/admin/bookings/{b2['id']}/status", json={"status": "cancelled", "refund": True}).raise_for_status()
    st.update(booking=b["id"], ref=b["reference_code"], booking2=b2["id"])
    json.dump(st, open(STATE, "w"))
    print(json.dumps({"booking": b["id"], "ref": b["reference_code"], "booking2": b2["id"]}))
else:
    st = json.load(open(STATE))
    new_b = [b["_id"] for b in db.bookings.find({"_id": {"$nin": st["bookings"]}})]
    db.financial_transactions.delete_many({"ref_type": "booking", "ref_id": {"$in": new_b}})
    db.commissions.delete_many({"booking_id": {"$in": new_b}})
    db.bookings.delete_many({"_id": {"$in": new_b}})
    db.booking_payments.delete_many({"_id": {"$nin": st["payments"]}})
    db.notifications.delete_many({"_id": {"$nin": st["notifs"]}})
    for k, v in st["read"].items():
        db.notifications.update_one({"_id": k}, {"$set": {"is_read": bool(v)}})
    db.customers.delete_many({"first_name": {"$regex": "^TEST_P7UI"}})
    from bson.decimal128 import Decimal128
    db.agent_profiles.update_one({"_id": AID}, {"$set": {"booking_account.balance": Decimal128(st["bal"])}})
    print("cleaned", len(new_b), db.agent_profiles.find_one({"_id": AID})["booking_account"]["balance"])
