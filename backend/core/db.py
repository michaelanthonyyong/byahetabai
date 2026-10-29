"""Central MongoDB client. Loaded once and reused by every module."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_ROOT / ".env")

_MONGO_URL = os.environ["MONGO_URL"]
_DB_NAME = os.environ["DB_NAME"]

_client: AsyncIOMotorClient = AsyncIOMotorClient(_MONGO_URL)
_db: AsyncIOMotorDatabase = _client[_DB_NAME]


def get_client() -> AsyncIOMotorClient:
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return _db


# Canonical collection names.  A single source of truth used by models,
# indexes, seed and verification.
class Collections:
    USERS = "users"
    AGENT_PROFILES = "agent_profiles"
    DESTINATIONS = "destinations"
    PACKAGES = "packages"
    CUSTOMERS = "customers"
    BOOKINGS = "bookings"
    TRANSACTIONS = "financial_transactions"
    FUND_REQUESTS = "fund_requests"
    COMMISSIONS = "commissions"
    COMMISSION_WITHDRAWALS = "commission_withdrawals"
    NOTIFICATIONS = "notifications"
    AUDIT_LOGS = "audit_logs"
    SETTINGS = "system_settings"
    CONTACT_MESSAGES = "contact_messages"
    AGENT_PACKAGE_MARKUPS = "agent_package_markups"
    BOOKING_PAYMENTS = "booking_payments"
    SHARE_LINKS = "share_links"

    @classmethod
    def all(cls) -> list[str]:
        return [
            cls.USERS, cls.AGENT_PROFILES, cls.DESTINATIONS, cls.PACKAGES,
            cls.CUSTOMERS, cls.BOOKINGS, cls.TRANSACTIONS, cls.FUND_REQUESTS,
            cls.COMMISSIONS, cls.COMMISSION_WITHDRAWALS, cls.NOTIFICATIONS,
            cls.AUDIT_LOGS, cls.SETTINGS, cls.CONTACT_MESSAGES, cls.AGENT_PACKAGE_MARKUPS, cls.BOOKING_PAYMENTS, cls.SHARE_LINKS,
            "auth_tokens", "login_attempts",
        ]
