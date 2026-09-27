"""Phase 4 Step 2 tests: Admin Destinations + Packages CRUD, publish workflow, public reflection."""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://agent-travel-desk-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "yongmichael992@gmail.com"
ADMIN_PASS = "Admin@12345"
DEMO_AGENT_EMAIL = "agent.demo@biyahetabai.example.com"
DEMO_AGENT_PASS = "Agent@12345"


@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def agent_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"demo agent login failed: {r.text}")
    return s


# ------------------- RBAC -------------------

class TestRBAC:
    def test_dest_unauth_401(self):
        r = requests.get(f"{API}/admin/destinations", timeout=10)
        assert r.status_code == 401

    def test_dest_agent_403(self, agent_sess):
        r = agent_sess.get(f"{API}/admin/destinations", timeout=10)
        assert r.status_code == 403

    def test_pkgs_unauth_401(self):
        r = requests.get(f"{API}/admin/packages", timeout=10)
        assert r.status_code == 401

    def test_pkgs_agent_403(self, agent_sess):
        r = agent_sess.get(f"{API}/admin/packages", timeout=10)
        assert r.status_code == 403

    def test_pkg_status_agent_403(self, agent_sess):
        r = agent_sess.post(f"{API}/admin/packages/anything/status", json={"status": "published"}, timeout=10)
        assert r.status_code == 403


# ------------------- Destinations list -------------------

class TestDestinationsList:
    def test_list_returns_seed(self, admin):
        r = admin.get(f"{API}/admin/destinations", timeout=15)
        assert r.status_code == 200
        slugs = [d["slug"] for d in r.json()["destinations"]]
        # Prior state: japan, south-korea, thailand, cebu, vietnam
        for s in ("japan", "south-korea", "thailand", "cebu"):
            assert s in slugs, f"Missing seed destination {s}"

    def test_package_counts_present(self, admin):
        r = admin.get(f"{API}/admin/destinations", timeout=15)
        data = r.json()["destinations"]
        japan = next((d for d in data if d["slug"] == "japan"), None)
        assert japan is not None
        assert "package_counts" in japan
        # japan has 2 packages per context
        total = sum((japan["package_counts"] or {}).values())
        assert total >= 2


# ------------------- Destinations CRUD -------------------

@pytest.fixture(scope="session")
def created_destination(admin):
    """Create a scratch destination for testing (palawan). Reused across tests."""
    slug = f"palawan-{uuid.uuid4().hex[:6]}"
    r = admin.post(
        f"{API}/admin/destinations",
        json={"slug": slug, "name": "Palawan Test", "country": "Philippines", "scope": "domestic"},
        timeout=15,
    )
    assert r.status_code == 201, r.text
    d = r.json()["destination"]
    yield d
    # cleanup best-effort
    admin.delete(f"{API}/admin/destinations/{d['id']}", timeout=10)


class TestDestinationCRUD:
    def test_create_success(self, created_destination):
        assert created_destination["slug"].startswith("palawan-")
        assert created_destination["scope"] == "domestic"

    def test_duplicate_slug_409(self, admin, created_destination):
        r = admin.post(
            f"{API}/admin/destinations",
            json={"slug": created_destination["slug"], "name": "Dup", "country": "PH", "scope": "domestic"},
            timeout=15,
        )
        assert r.status_code == 409

    def test_patch_toggle_active(self, admin, created_destination):
        did = created_destination["id"]
        r = admin.patch(f"{API}/admin/destinations/{did}", json={"is_active": False}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("changed") is True
        # Verify
        r2 = admin.get(f"{API}/admin/destinations/{did}", timeout=10)
        assert r2.json()["destination"]["is_active"] is False
        # Restore
        admin.patch(f"{API}/admin/destinations/{did}", json={"is_active": True}, timeout=15)

    def test_delete_with_linked_packages_409(self, admin):
        r = admin.get(f"{API}/admin/destinations", timeout=15)
        japan = next(d for d in r.json()["destinations"] if d["slug"] == "japan")
        r2 = admin.delete(f"{API}/admin/destinations/{japan['id']}", timeout=15)
        assert r2.status_code == 409


# ------------------- Packages list -------------------

class TestPackagesList:
    def test_list_shape(self, admin):
        r = admin.get(f"{API}/admin/packages", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "packages" in data and "total" in data
        assert data["total"] >= 5
        p0 = data["packages"][0]
        # compact list view: no embedded arrays
        assert "images" not in p0
        assert "inclusions" not in p0
        assert "exclusions" not in p0
        assert "destination" in p0
        assert "booking_count" in p0

    def test_search_osaka(self, admin):
        r = admin.get(f"{API}/admin/packages", params={"q": "osaka"}, timeout=15)
        assert r.status_code == 200
        slugs = [p["slug"] for p in r.json()["packages"]]
        assert any("osaka" in s for s in slugs)

    def test_search_empty(self, admin):
        r = admin.get(f"{API}/admin/packages", params={"q": "zzzzz"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_filter_draft(self, admin):
        r = admin.get(f"{API}/admin/packages", params={"status": "draft"}, timeout=15)
        assert r.status_code == 200
        pkgs = r.json()["packages"]
        assert all(p["status"] == "draft" for p in pkgs)
        assert any(p["slug"] == "japan-sakura-preview" for p in pkgs)


# ------------------- Package create + publish flow -------------------

@pytest.fixture(scope="session")
def thailand_id(admin):
    r = admin.get(f"{API}/admin/destinations", timeout=15)
    return next(d["id"] for d in r.json()["destinations"] if d["slug"] == "thailand")


@pytest.fixture(scope="session")
def phuket_pkg(admin, thailand_id):
    slug = f"phuket-4d3n-{uuid.uuid4().hex[:6]}"
    r = admin.post(
        f"{API}/admin/packages",
        json={
            "slug": slug,
            "title": "Phuket 4D3N Test",
            "destination_id": thailand_id,
            "guest_price": "19999",
            "agent_cost": "17000",
            "commission_amount": "1200",
            "duration_days": 4,
            "duration_nights": 3,
            "min_pax": 2,
            "max_pax": 15,
            "images": [],
            "inclusions": [],
            "exclusions": [],
        },
        timeout=15,
    )
    assert r.status_code == 201, r.text
    pkg = r.json()["package"]
    yield pkg
    # cleanup (may 409 if published & booked)
    admin.delete(f"{API}/admin/packages/{pkg['id']}", timeout=10)


class TestPackageCreatePublish:
    def test_create_defaults_draft(self, phuket_pkg):
        assert phuket_pkg["status"] == "draft"

    def test_publish_no_images_400(self, admin, phuket_pkg):
        r = admin.post(f"{API}/admin/packages/{phuket_pkg['id']}/status", json={"status": "published"}, timeout=15)
        assert r.status_code == 400
        assert "image" in r.json()["detail"].lower()

    def test_add_image_then_publish_needs_inclusion(self, admin, phuket_pkg):
        r = admin.patch(
            f"{API}/admin/packages/{phuket_pkg['id']}",
            json={"images": [{"url": "https://images.example.com/phuket.jpg", "is_cover": True, "sort_order": 0}]},
            timeout=15,
        )
        assert r.status_code == 200
        # now publish should fail on missing inclusions
        r2 = admin.post(f"{API}/admin/packages/{phuket_pkg['id']}/status", json={"status": "published"}, timeout=15)
        assert r2.status_code == 400
        assert "inclusion" in r2.json()["detail"].lower()

    def test_add_inclusion_then_publish_ok(self, admin, phuket_pkg):
        r = admin.patch(
            f"{API}/admin/packages/{phuket_pkg['id']}",
            json={
                "inclusions": [{"text": "Airfare", "sort_order": 0}],
                "exclusions": [{"text": "Travel insurance", "sort_order": 0}],
            },
            timeout=15,
        )
        assert r.status_code == 200
        r2 = admin.post(f"{API}/admin/packages/{phuket_pkg['id']}/status", json={"status": "published"}, timeout=15)
        assert r2.status_code == 200
        # verify status
        r3 = admin.get(f"{API}/admin/packages/{phuket_pkg['id']}", timeout=10)
        assert r3.json()["package"]["status"] == "published"

    def test_published_reflected_on_public(self, phuket_pkg):
        r = requests.get(f"{API}/public/packages", timeout=15)
        assert r.status_code == 200
        # public listing returns packages list
        payload = r.json()
        pkgs = payload.get("packages", payload) if isinstance(payload, dict) else payload
        slugs = [p["slug"] for p in pkgs]
        assert phuket_pkg["slug"] in slugs

    def test_edit_title_persists(self, admin, phuket_pkg):
        new_title = f"Phuket Updated {uuid.uuid4().hex[:4]}"
        r = admin.patch(f"{API}/admin/packages/{phuket_pkg['id']}", json={"title": new_title}, timeout=15)
        assert r.status_code == 200
        r2 = admin.get(f"{API}/admin/packages/{phuket_pkg['id']}", timeout=10)
        assert r2.json()["package"]["title"] == new_title

    def test_max_pax_less_than_min_400(self, admin, phuket_pkg):
        r = admin.patch(f"{API}/admin/packages/{phuket_pkg['id']}", json={"min_pax": 10, "max_pax": 2}, timeout=15)
        assert r.status_code == 400

    def test_archive_removes_from_public(self, admin, phuket_pkg):
        r = admin.post(f"{API}/admin/packages/{phuket_pkg['id']}/status", json={"status": "archived"}, timeout=15)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/public/packages", timeout=15)
        payload = r2.json()
        pkgs = payload.get("packages", payload) if isinstance(payload, dict) else payload
        slugs = [p["slug"] for p in pkgs]
        assert phuket_pkg["slug"] not in slugs


# ------------------- Delete guard -------------------

class TestDeleteGuard:
    def test_delete_with_booking_409(self, admin):
        r = admin.get(f"{API}/admin/packages", params={"q": "bangkok-pattaya"}, timeout=15)
        pkgs = r.json()["packages"]
        if not pkgs:
            pytest.skip("bangkok-pattaya package not present")
        pid = pkgs[0]["id"]
        r2 = admin.delete(f"{API}/admin/packages/{pid}", timeout=15)
        # If booking exists (previous test cancelled it but the booking row remains) -> 409
        assert r2.status_code == 409


# ------------------- Public detail smoke -------------------

class TestPublicSmoke:
    def test_public_destinations_ok(self):
        r = requests.get(f"{API}/public/destinations", timeout=15)
        assert r.status_code == 200

    def test_admin_dashboard_still_ok(self, admin):
        r = admin.get(f"{API}/admin/dashboard", timeout=15)
        assert r.status_code == 200
