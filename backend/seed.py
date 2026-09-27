"""Idempotent seed data for Biyahe'Ta Bai Travel (Phase 1).

Rules
-----
* Every insert is guarded by a natural-key lookup so re-running is a no-op.
* Only the smallest amount of data required to exercise the schema.
* All monetary values are strings converted to Decimal via the model layer,
  which stores them as Decimal128.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from decimal import Decimal
from typing import Optional

import bcrypt

from core.db import Collections, get_db
from core.init_db import init_db
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")
from models import (
    AgentAccount, AgentProfile, AgentStatus,
    AuditLog,
    Booking, BookingStatus, BookingStatusHistoryEntry, BookingTraveler, GuestPaymentStatus,
    Commission, CommissionStatus,
    Customer,
    Destination, DestinationScope,
    FinancialTransaction, TransactionType,
    FundRequest, FundRequestStatus,
    Notification,
    Package, PackageExclusion, PackageImage, PackageInclusion, PackageStatus,
    User, UserRole, UserStatus,
)

logger = logging.getLogger(__name__)


# --- helpers ---------------------------------------------------------------

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


async def _get_by(collection: str, **query):
    return await get_db()[collection].find_one(query)


async def _insert_if_absent(collection: str, natural_key: dict, document) -> tuple[bool, str]:
    """Insert ``document.to_mongo()`` unless a matching natural-key row exists.

    Returns ``(inserted, existing_or_new_id)``.
    """
    existing = await get_db()[collection].find_one(natural_key)
    if existing:
        return False, existing["_id"]
    doc = document.to_mongo()
    await get_db()[collection].insert_one(doc)
    return True, doc["_id"]


# --- seeders ---------------------------------------------------------------

async def seed_users_and_admin() -> str:
    """Ensure the master admin exists.  Returns admin user_id."""
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@biyahetabai.example.com").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@12345")
    admin_name = os.environ.get("ADMIN_DISPLAY_NAME", "Master Admin")

    existing = await _get_by(Collections.USERS, email=admin_email)
    if existing:
        # If password in env changed, sync the hash so login always works.
        import bcrypt as _bcrypt
        current_ok = _bcrypt.checkpw(
            admin_password.encode("utf-8"),
            existing["password_hash"].encode("utf-8"),
        )
        if not current_ok:
            await get_db()[Collections.USERS].update_one(
                {"_id": existing["_id"]},
                {"$set": {"password_hash": _hash_password(admin_password)}},
            )
        return existing["_id"]

    admin = User(
        email=admin_email,
        password_hash=_hash_password(admin_password),
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        display_name=admin_name,
    )
    doc = admin.to_mongo()
    await get_db()[Collections.USERS].insert_one(doc)
    return doc["_id"]


async def seed_demo_agent(admin_user_id: str) -> tuple[str, str]:
    """Create one demo agent user + profile. Returns (user_id, agent_profile_id)."""
    agent_email = "agent.demo@biyahetabai.example.com"
    existing_user = await _get_by(Collections.USERS, email=agent_email)

    if existing_user:
        user_id = existing_user["_id"]
    else:
        agent_user = User(
            email=agent_email,
            password_hash=_hash_password("Agent@12345"),
            role=UserRole.AGENT,
            status=UserStatus.ACTIVE,
            display_name="Demo Agent",
            created_by_user_id=admin_user_id,
        )
        doc = agent_user.to_mongo()
        await get_db()[Collections.USERS].insert_one(doc)
        user_id = doc["_id"]

    existing_profile = await _get_by(Collections.AGENT_PROFILES, user_id=user_id)
    if existing_profile:
        return user_id, existing_profile["_id"]

    profile = AgentProfile(
        user_id=user_id,
        display_name="Demo Agent",
        agency_name="Demo Travel Agency",
        phone="+63 900 000 0000",
        address="Cebu City, Philippines",
        status=AgentStatus.ACTIVE,
        booking_account=AgentAccount(kind="booking", balance=Decimal("0.00")),
        commission_account=AgentAccount(kind="commission", balance=Decimal("0.00")),
        created_by_user_id=admin_user_id,
    )
    doc = profile.to_mongo()
    await get_db()[Collections.AGENT_PROFILES].insert_one(doc)
    return user_id, doc["_id"]


DESTINATIONS_SEED = [
    dict(
        slug="japan", name="Japan", country="Japan",
        scope=DestinationScope.INTERNATIONAL,
        hero_image_url="https://images.unsplash.com/photo-1542051841857-5f90071e7989?q=80&w=1200",
        short_description="Cherry blossoms, temples, and neon skylines.",
        featured_on_home=True,
    ),
    dict(
        slug="south-korea", name="South Korea", country="South Korea",
        scope=DestinationScope.INTERNATIONAL,
        hero_image_url="https://images.unsplash.com/photo-1583833008338-31a6657917ab?q=80&w=1200",
        short_description="K-culture, palaces, and Seoul's electric nights.",
        featured_on_home=True,
    ),
    dict(
        slug="thailand", name="Thailand", country="Thailand",
        scope=DestinationScope.INTERNATIONAL,
        hero_image_url="https://images.unsplash.com/photo-1528181304800-259b08848526?q=80&w=1200",
        short_description="Golden temples, bustling markets, and island shores.",
        featured_on_home=True,
    ),
    dict(
        slug="cebu", name="Cebu", country="Philippines",
        scope=DestinationScope.DOMESTIC,
        hero_image_url="https://images.unsplash.com/photo-1583417319070-4a69db38a482?q=80&w=1200",
        short_description="Queen City of the South — beaches, heritage, and adventure.",
        featured_on_home=True,
    ),
]


async def seed_destinations() -> dict[str, str]:
    """Returns slug → destination_id map."""
    ids: dict[str, str] = {}
    for spec in DESTINATIONS_SEED:
        dest = Destination(**spec)
        _, dest_id = await _insert_if_absent(
            Collections.DESTINATIONS, {"slug": dest.slug}, dest
        )
        ids[dest.slug] = dest_id
    return ids


def _pkg_image(url: str, is_cover: bool = False, order: int = 0) -> PackageImage:
    return PackageImage(id=str(uuid.uuid4()), url=url, is_cover=is_cover, sort_order=order)


def _incl(text: str, order: int) -> PackageInclusion:
    return PackageInclusion(id=str(uuid.uuid4()), text=text, sort_order=order)


def _excl(text: str, order: int) -> PackageExclusion:
    return PackageExclusion(id=str(uuid.uuid4()), text=text, sort_order=order)


def _packages_seed(dest_ids: dict[str, str]) -> list[Package]:
    return [
        Package(
            slug="osaka-kyoto-nara-5d4n",
            title="Osaka Kyoto Nara 5D4N Tour",
            destination_id=dest_ids["japan"],
            guest_price=Decimal("44888.00"),
            agent_cost=Decimal("39888.00"),
            commission_amount=Decimal("2000.00"),
            duration_days=5, duration_nights=4,
            min_pax=2, max_pax=10,
            summary="Kansai's greatest hits in five vibrant days.",
            itinerary="Day 1 Osaka arrival • Day 2 Kyoto temples • Day 3 Nara deer park • Day 4 Universal Studios • Day 5 departure",
            images=[
                _pkg_image(
                    "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?q=80&w=1200",
                    is_cover=True, order=0,
                ),
                _pkg_image(
                    "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?q=80&w=1200",
                    order=1,
                ),
            ],
            inclusions=[
                _incl("Round-trip airfare from Manila", 0),
                _incl("4 nights hotel accommodation", 1),
                _incl("Daily breakfast", 2),
                _incl("English-speaking tour guide", 3),
            ],
            exclusions=[
                _excl("Travel insurance", 0),
                _excl("Personal expenses", 1),
            ],
            status=PackageStatus.PUBLISHED, is_featured=True,
        ),
        Package(
            slug="seoul-nami-everland-5d4n",
            title="Seoul Nami Everland 5D4N Tour",
            destination_id=dest_ids["south-korea"],
            guest_price=Decimal("39888.00"),
            agent_cost=Decimal("35000.00"),
            commission_amount=Decimal("1800.00"),
            duration_days=5, duration_nights=4,
            min_pax=2, max_pax=15,
            summary="Palaces, Nami Island autumn, and Everland thrills.",
            images=[
                _pkg_image(
                    "https://images.unsplash.com/photo-1548115184-bc6544d06a58?q=80&w=1200",
                    is_cover=True, order=0,
                ),
            ],
            inclusions=[_incl("Round-trip airfare", 0), _incl("Hotel + breakfast", 1)],
            exclusions=[_excl("Visa fees", 0)],
            status=PackageStatus.PUBLISHED, is_featured=True,
        ),
        Package(
            slug="bangkok-pattaya-4d3n",
            title="Bangkok Pattaya 4D3N Tour",
            destination_id=dest_ids["thailand"],
            guest_price=Decimal("22888.00"),
            agent_cost=Decimal("19500.00"),
            commission_amount=Decimal("1200.00"),
            duration_days=4, duration_nights=3,
            min_pax=2, max_pax=20,
            summary="Temples, tuk-tuks, and turquoise coast in one trip.",
            images=[
                _pkg_image(
                    "https://images.unsplash.com/photo-1508009603885-50cf7c579365?q=80&w=1200",
                    is_cover=True, order=0,
                ),
            ],
            inclusions=[_incl("Round-trip airfare", 0)],
            exclusions=[_excl("Tips", 0)],
            status=PackageStatus.PUBLISHED, is_featured=True,
        ),
        Package(
            slug="cebu-free-and-easy-4d3n",
            title="4D3N Cebu Free & Easy",
            destination_id=dest_ids["cebu"],
            guest_price=Decimal("4069.00"),
            agent_cost=Decimal("3500.00"),
            commission_amount=Decimal("300.00"),
            duration_days=4, duration_nights=3,
            min_pax=1, max_pax=10,
            summary="Explore the Queen City on your own pace.",
            images=[
                _pkg_image(
                    "https://images.unsplash.com/photo-1583417319070-4a69db38a482?q=80&w=1200",
                    is_cover=True, order=0,
                ),
            ],
            inclusions=[_incl("Hotel accommodation", 0)],
            exclusions=[_excl("Airfare", 0)],
            status=PackageStatus.PUBLISHED, is_featured=False,
        ),
        # A draft package to exercise the status filter.
        Package(
            slug="japan-sakura-preview",
            title="Japan Sakura Preview (draft)",
            destination_id=dest_ids["japan"],
            guest_price=Decimal("49999.00"),
            agent_cost=Decimal("45000.00"),
            commission_amount=Decimal("2200.00"),
            duration_days=6, duration_nights=5,
            summary="Cherry-blossom itinerary — not yet published.",
            status=PackageStatus.DRAFT,
        ),
    ]


async def seed_packages(dest_ids: dict[str, str]) -> dict[str, str]:
    """Returns slug → package_id map."""
    ids: dict[str, str] = {}
    for pkg in _packages_seed(dest_ids):
        _, pkg_id = await _insert_if_absent(
            Collections.PACKAGES, {"slug": pkg.slug}, pkg
        )
        ids[pkg.slug] = pkg_id
    return ids


async def seed_customer_booking_transactions(
    admin_user_id: str, agent_user_id: str, agent_id: str, packages: dict[str, str]
) -> None:
    """Seed a demo lifecycle end-to-end to verify FKs and financial invariants.

    Sequence:
        1. Approved fund request +50,000 → booking account 50,000
        2. Customer created
        3. Booking created (4 pax × 19,500 agent_cost) → 78,000 debit
           NOTE: this exceeds the top-up on purpose to demonstrate the
           balance-goes-negative check is a service-layer concern (Phase 5+),
           not a schema concern.  We therefore only book 2 pax here.
        4. Commission accrual on confirmed booking → commission account +
    """
    db = get_db()

    # Skip if the demo booking already exists.
    if await db[Collections.BOOKINGS].find_one({"reference_code": "BTB-DEMO-0001"}):
        return

    # --- 1. Fund request -------------------------------------------------
    fund = FundRequest(
        agent_id=agent_id,
        amount=Decimal("50000.00"),
        reference_no="DEMO-DEP-0001",
        note="Demo seed top-up",
        status=FundRequestStatus.APPROVED,
        decided_by_user_id=admin_user_id,
        decided_at=fund_iso(),
        decision_note="Approved by seed",
    )
    top_up_txn = FinancialTransaction(
        agent_id=agent_id, account_kind="booking",
        type=TransactionType.TOP_UP,
        amount=Decimal("50000.00"),
        balance_after=Decimal("50000.00"),
        ref_type="fund_request", ref_id=fund.id,
        idempotency_key=f"seed-topup-{fund.id}",
        created_by_user_id=admin_user_id,
        note="Seed approval",
    )
    fund.transaction_id = top_up_txn.id
    await db[Collections.FUND_REQUESTS].insert_one(fund.to_mongo())
    await db[Collections.TRANSACTIONS].insert_one(top_up_txn.to_mongo())
    await db[Collections.AGENT_PROFILES].update_one(
        {"_id": agent_id},
        {"$set": {"booking_account.balance": top_up_txn.to_mongo()["balance_after"]}},
    )
    await db[Collections.AUDIT_LOGS].insert_one(
        AuditLog(
            actor_user_id=admin_user_id, actor_role="admin",
            action="fund_request.approve",
            target_type="fund_request", target_id=fund.id,
            after={"status": "approved", "amount": "50000.00"},
            note="Seed",
        ).to_mongo()
    )

    # --- 2. Customer -----------------------------------------------------
    customer = Customer(
        agent_id=agent_id,
        first_name="Juan", last_name="dela Cruz",
        email="juan.delacruz@example.com", phone="+63 917 555 0100",
    )
    await db[Collections.CUSTOMERS].insert_one(customer.to_mongo())

    # --- 3. Booking (2 pax × Bangkok Pattaya) ----------------------------
    pkg_id = packages["bangkok-pattaya-4d3n"]
    pkg_doc = await db[Collections.PACKAGES].find_one({"_id": pkg_id})
    from models.base import money_from_bson
    unit_agent_cost = money_from_bson(pkg_doc["agent_cost"])
    unit_guest_price = money_from_bson(pkg_doc["guest_price"])
    unit_commission = money_from_bson(pkg_doc["commission_amount"])
    pax = 2
    total_agent_cost = (unit_agent_cost * pax).quantize(Decimal("0.01"))
    total_guest_price = (unit_guest_price * pax).quantize(Decimal("0.01"))
    total_commission = (unit_commission * pax).quantize(Decimal("0.01"))

    booking = Booking(
        reference_code="BTB-DEMO-0001",
        agent_id=agent_id,
        customer_id=customer.id,
        package_id=pkg_id,
        pax=pax,
        unit_agent_cost=unit_agent_cost,
        unit_guest_price=unit_guest_price,
        unit_commission_amount=unit_commission,
        total_agent_cost=total_agent_cost,
        total_guest_price=total_guest_price,
        total_commission_amount=total_commission,
        status=BookingStatus.CONFIRMED,
        guest_payment_status=GuestPaymentStatus.PAID,
        travelers=[
            BookingTraveler(full_name="Juan dela Cruz", is_lead=True),
            BookingTraveler(full_name="Maria dela Cruz"),
        ],
        status_history=[
            BookingStatusHistoryEntry(to_status=BookingStatus.PENDING, changed_by_user_id=agent_user_id, note="Created"),
            BookingStatusHistoryEntry(from_status=BookingStatus.PENDING, to_status=BookingStatus.CONFIRMED, changed_by_user_id=admin_user_id, note="Confirmed by admin"),
        ],
        notes="Demo seed booking",
    )
    debit_txn = FinancialTransaction(
        agent_id=agent_id, account_kind="booking",
        type=TransactionType.BOOKING_DEBIT,
        amount=-total_agent_cost,
        balance_after=(Decimal("50000.00") - total_agent_cost).quantize(Decimal("0.01")),
        ref_type="booking", ref_id=booking.id,
        idempotency_key=f"seed-debit-{booking.id}",
        created_by_user_id=agent_user_id,
        note="Seed booking debit",
    )
    accrual_txn = FinancialTransaction(
        agent_id=agent_id, account_kind="commission",
        type=TransactionType.COMMISSION_ACCRUAL,
        amount=total_commission,
        balance_after=total_commission,
        ref_type="booking", ref_id=booking.id,
        idempotency_key=f"seed-accrual-{booking.id}",
        created_by_user_id=admin_user_id,
        note="Seed commission accrual",
    )
    commission = Commission(
        agent_id=agent_id,
        booking_id=booking.id,
        amount=total_commission,
        status=CommissionStatus.ACCRUED,
        accrual_transaction_id=accrual_txn.id,
    )

    await db[Collections.BOOKINGS].insert_one(booking.to_mongo())
    await db[Collections.TRANSACTIONS].insert_many(
        [debit_txn.to_mongo(), accrual_txn.to_mongo()]
    )
    await db[Collections.COMMISSIONS].insert_one(commission.to_mongo())
    await db[Collections.AGENT_PROFILES].update_one(
        {"_id": agent_id},
        {"$set": {
            "booking_account.balance": debit_txn.to_mongo()["balance_after"],
            "commission_account.balance": accrual_txn.to_mongo()["balance_after"],
        }},
    )
    await db[Collections.AUDIT_LOGS].insert_many([
        AuditLog(
            actor_user_id=agent_user_id, actor_role="agent",
            action="booking.create",
            target_type="booking", target_id=booking.id,
            after={"pax": pax, "total_agent_cost": str(total_agent_cost)},
            note="Seed",
        ).to_mongo(),
        AuditLog(
            actor_user_id=admin_user_id, actor_role="admin",
            action="booking.confirm",
            target_type="booking", target_id=booking.id,
            after={"status": "confirmed"},
            note="Seed",
        ).to_mongo(),
    ])
    await db[Collections.NOTIFICATIONS].insert_one(
        Notification(
            user_id=agent_user_id,
            title="Booking confirmed",
            body=f"Booking {booking.reference_code} has been confirmed by admin.",
            ref_type="booking", ref_id=booking.id,
        ).to_mongo()
    )


def fund_iso() -> str:
    from models.base import utc_now_iso
    return utc_now_iso()


# --- entry point -----------------------------------------------------------

async def run_seed() -> dict:
    await init_db()
    admin_id = await seed_users_and_admin()
    agent_user_id, agent_profile_id = await seed_demo_agent(admin_id)
    dest_ids = await seed_destinations()
    pkg_ids = await seed_packages(dest_ids)
    await seed_customer_booking_transactions(admin_id, agent_user_id, agent_profile_id, pkg_ids)
    return {
        "admin_user_id": admin_id,
        "agent_user_id": agent_user_id,
        "agent_profile_id": agent_profile_id,
        "destinations": dest_ids,
        "packages": pkg_ids,
    }


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(run_seed()))
