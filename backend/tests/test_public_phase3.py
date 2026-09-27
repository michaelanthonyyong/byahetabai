"""Phase 3 public catalog API tests."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://agent-travel-desk-1.preview.emergentagent.com"


@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- destinations ---
class TestDestinations:
    def test_list_destinations(self, api):
        r = api.get(f"{BASE_URL}/api/public/destinations")
        assert r.status_code == 200
        data = r.json()
        assert "destinations" in data
        slugs = {d["slug"] for d in data["destinations"]}
        assert {"japan", "south-korea", "thailand", "cebu"}.issubset(slugs)
        # No agent-only fields
        for d in data["destinations"]:
            assert "agent_cost" not in d
            assert "commission_amount" not in d

    def test_get_destination_japan(self, api):
        r = api.get(f"{BASE_URL}/api/public/destinations/japan")
        assert r.status_code == 200
        data = r.json()
        assert data["destination"]["slug"] == "japan"
        pkgs = data["packages"]
        assert any(p["slug"] == "osaka-kyoto-nara-5d4n" for p in pkgs)
        # draft must be hidden
        assert not any(p["slug"] == "japan-sakura-preview" for p in pkgs)
        for p in pkgs:
            assert "agent_cost" not in p
            assert "commission_amount" not in p

    def test_get_destination_not_found(self, api):
        r = api.get(f"{BASE_URL}/api/public/destinations/does-not-exist")
        assert r.status_code == 404


# --- packages ---
class TestPackages:
    def test_list_packages_all(self, api):
        r = api.get(f"{BASE_URL}/api/public/packages")
        assert r.status_code == 200
        data = r.json()
        slugs = {p["slug"] for p in data["packages"]}
        # 4 published
        assert {"osaka-kyoto-nara-5d4n", "seoul-nami-everland-5d4n",
                "bangkok-pattaya-4d3n", "cebu-free-and-easy-4d3n"}.issubset(slugs)
        # draft hidden
        assert "japan-sakura-preview" not in slugs
        for p in data["packages"]:
            assert "agent_cost" not in p
            assert "commission_amount" not in p

    def test_list_international_scope(self, api):
        r = api.get(f"{BASE_URL}/api/public/packages", params={"scope": "international"})
        assert r.status_code == 200
        pkgs = r.json()["packages"]
        assert len(pkgs) == 3
        for p in pkgs:
            assert p["destination"]["scope"] == "international"

    def test_list_domestic_scope(self, api):
        r = api.get(f"{BASE_URL}/api/public/packages", params={"scope": "domestic"})
        assert r.status_code == 200
        pkgs = r.json()["packages"]
        assert len(pkgs) == 1
        assert pkgs[0]["slug"] == "cebu-free-and-easy-4d3n"

    def test_search_osaka(self, api):
        r = api.get(f"{BASE_URL}/api/public/packages", params={"q": "osaka"})
        assert r.status_code == 200
        pkgs = r.json()["packages"]
        assert len(pkgs) == 1
        assert pkgs[0]["slug"] == "osaka-kyoto-nara-5d4n"

    def test_filter_by_destination(self, api):
        r = api.get(f"{BASE_URL}/api/public/packages", params={"destination": "japan"})
        assert r.status_code == 200
        pkgs = r.json()["packages"]
        assert len(pkgs) >= 1
        for p in pkgs:
            assert p["destination"]["slug"] == "japan"

    def test_get_package_detail(self, api):
        r = api.get(f"{BASE_URL}/api/public/packages/osaka-kyoto-nara-5d4n")
        assert r.status_code == 200
        pkg = r.json()["package"]
        assert pkg["slug"] == "osaka-kyoto-nara-5d4n"
        assert pkg["guest_price"]
        assert isinstance(pkg["inclusions"], list) and len(pkg["inclusions"]) > 0
        assert isinstance(pkg["exclusions"], list)
        assert isinstance(pkg["images"], list)
        assert "agent_cost" not in pkg
        assert "commission_amount" not in pkg

    def test_get_package_draft_hidden(self, api):
        r = api.get(f"{BASE_URL}/api/public/packages/japan-sakura-preview")
        assert r.status_code == 404

    def test_get_package_not_found(self, api):
        r = api.get(f"{BASE_URL}/api/public/packages/does-not-exist")
        assert r.status_code == 404


# --- brand + contact ---
class TestBrandContact:
    def test_brand(self, api):
        r = api.get(f"{BASE_URL}/api/public/brand")
        assert r.status_code == 200
        assert "brand" in r.json()

    def test_contact_valid(self, api):
        r = api.post(f"{BASE_URL}/api/public/contact", json={
            "name": "TEST User",
            "email": "test_phase3@example.com",
            "message": "Hello, I'd like info.",
        })
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_contact_with_package_slug(self, api):
        r = api.post(f"{BASE_URL}/api/public/contact", json={
            "name": "TEST User 2",
            "email": "test_phase3_pkg@example.com",
            "message": "Interested in Osaka",
            "package_slug": "osaka-kyoto-nara-5d4n",
        })
        assert r.status_code == 200

    def test_contact_invalid_email(self, api):
        r = api.post(f"{BASE_URL}/api/public/contact", json={
            "name": "X", "email": "not-an-email", "message": "hi"
        })
        assert r.status_code == 422

    def test_contact_empty_message(self, api):
        r = api.post(f"{BASE_URL}/api/public/contact", json={
            "name": "X", "email": "a@b.com", "message": ""
        })
        assert r.status_code == 422


# --- Phase 2 auth still works ---
class TestPhase2AuthIntact:
    def test_admin_login(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login", json={
            "email": "yongmichael992@gmail.com",
            "password": "Admin@12345",
        })
        assert r.status_code == 200
        data = r.json()
        assert data.get("user", {}).get("role") == "admin"
