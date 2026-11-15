"""Rename the master admin's login email and/or display name, in place.

Changing ADMIN_EMAIL in .env alone is not enough: seed.py looks the admin up
by email, so a new email would create a *second* admin and leave the old
login active. This script updates the existing admin account instead, so its
id — and therefore its audit-log history — is preserved.

Usage (from the backend folder):
    .venv/Scripts/python scripts/update_admin.py --email new@example.com --name "Admin"
    .venv/Scripts/python scripts/update_admin.py --name "Admin"        # name only
    ... --from-email old@example.com   # which admin to rename (default: ADMIN_EMAIL from .env)

Afterwards, set ADMIN_EMAIL / ADMIN_DISPLAY_NAME in .env to the new values so
seed.py keeps matching this account.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from email_validator import EmailNotValidError, validate_email  # noqa: E402

from core.db import Collections, get_db  # noqa: E402
from models.audit_log import AuditLog  # noqa: E402
from models.base import utc_now_iso  # noqa: E402


async def main(args: argparse.Namespace) -> int:
    db = get_db()
    users = db[Collections.USERS]
    from_email = (args.from_email or os.environ.get("ADMIN_EMAIL", "")).lower().strip()
    if not from_email:
        print("No admin to rename: pass --from-email or set ADMIN_EMAIL in .env")
        return 1

    admin = await users.find_one({"email": from_email, "role": "admin"})
    if not admin:
        print(f"No admin account with email {from_email!r} found in database {os.environ.get('DB_NAME')!r}")
        return 1

    changes: dict = {}
    if args.email:
        try:
            new_email = validate_email(args.email, check_deliverability=False).normalized.lower()
        except EmailNotValidError as e:
            print(f"Invalid email: {e}")
            return 1
        if new_email != admin["email"]:
            if await users.find_one({"email": new_email, "_id": {"$ne": admin["_id"]}}):
                print(f"Another account already uses {new_email!r}; nothing changed")
                return 1
            changes["email"] = new_email
    if args.name is not None:
        name = args.name.strip()
        if not name or len(name) > 120:
            print("Display name must be 1-120 characters")
            return 1
        if name != admin.get("display_name"):
            changes["display_name"] = name

    if not changes:
        print("Nothing to change.")
        return 0

    before = {k: admin.get(k) for k in changes}
    await users.update_one({"_id": admin["_id"]}, {"$set": {**changes, "updated_at": utc_now_iso()}})
    await db[Collections.AUDIT_LOGS].insert_one(AuditLog(
        actor_user_id=admin["_id"], actor_role="admin",
        action="admin.profile.update", target_type="user", target_id=admin["_id"],
        before=before, after=changes, user_agent="scripts/update_admin.py",
        note="Master admin renamed via maintenance script",
    ).to_mongo())
    for k, v in changes.items():
        print(f"{k}: {before[k]!r} -> {v!r}")
    print("Done. Now update ADMIN_EMAIL / ADMIN_DISPLAY_NAME in .env to match.")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--email", help="new login email")
    p.add_argument("--name", help="new display name")
    p.add_argument("--from-email", help="current admin email (default: ADMIN_EMAIL from .env)")
    sys.exit(asyncio.run(main(p.parse_args())))
