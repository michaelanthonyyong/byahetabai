"""UI seed for phase 9: TEST_P9UI customer + booking + payment. `python ui_setup_phase9.py [cleanup]`"""
import os
import sys
from datetime import date, timedelta

import requests
from dotenv import load_dotenv
from bson.decimal128 import Decimal128
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
u = db.users.find_one({"email": "agent.demo@biyahetabai.example.com"})
prof = db.agent_profiles.find_one({"user_id": u["_id"]})

if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    cids = [c["_id"] for c in db.customers.find({"first_name": {"$regex": "^TEST_P9UI"}})]
    bids = [b["_id"] for b in db.bookings.find({"customer_id": {"$in": cids}})]
    db.financial_transactions.delete_many({"ref_type": "booking", "ref_id": {"$in": bids}})
    db.commissions.delete_many({"booking_id": {"$in": bids}})
    db.booking_payments.delete_many({"booking_id": {"$in": bids}})
    db.notifications.delete_many({"ref_id": {"$in": bids}})
    db.bookings.delete_many({"_id": {"$in": bids}})
    db.customers.delete_many({"_id": {"$in": cids}})
    db.agent_profiles.update_one({"_id": prof["_id"]}, {"$set": {"booking_account.balance": Decimal128(sys.argv[2])}})
    print("cleaned", bids)
    sys.exit()

print("balance", prof["booking_account"]["balance"], "brand", prof.get("brand_color"))
s = requests.Session()
s.post(f"{API}/auth/login", json={"email": "agent.demo@biyahetabai.example.com", "password": "Agent@12345"})
c = s.post(f"{API}/agent/customers", json={"first_name": "TEST_P9UI_Lea", "last_name": "Santos"}).json()["customer"]
b = s.post(f"{API}/agent/bookings", json={"customer_id": c["id"], "package_id": "4c02efb1-1bc8-4a09-8636-0a49020f42f4",
           "pax": 1, "travel_start_date": (date.today() + timedelta(days=25)).isoformat(), "traveler_names": ["TEST_P9UI T"]}).json()["booking"]
p = s.post(f"{API}/agent/bookings/{b['id']}/payments", json={"amount": "1000", "method": "cash", "paid_on": date.today().isoformat()}).json()["payments"][-1]
print("BOOKING", b["id"], "PAYMENT", p["id"])
