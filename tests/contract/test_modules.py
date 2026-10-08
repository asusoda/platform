"""Orgs can turn optional modules off; a turned-off module's org routes return 404."""

import pytest


def _soda_id(client, officer_headers):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    return next(o["id"] for o in orgs if o["prefix"] == "soda")


@pytest.fixture
def soda_id(client, officer_headers, restore_soda_config):
    return _soda_id(client, officer_headers)


def test_modules_are_on_by_default(client, officer_headers, soda_id):
    response = client.get(f"/api/organizations/{soda_id}/modules", headers=officer_headers)
    assert response.status_code == 200
    assert {m["name"]: m["enabled"] for m in response.get_json()["modules"]} == {
        "points": True,
        "storefront": True,
        "calendar": True,
    }


def test_turned_off_module_returns_404(client, officer_headers, soda_id):
    assert client.get("/api/storefront/soda/products").status_code == 200
    response = client.put(
        f"/api/organizations/{soda_id}/modules", json={"modules": {"storefront": False}}, headers=officer_headers
    )
    assert response.status_code == 200
    assert client.get("/api/storefront/soda/products").status_code == 404
    # Other orgs and other modules are unaffected
    assert client.get("/api/storefront/ais/products").status_code == 200
    assert client.get("/api/public/soda/leaderboard").status_code == 200


def test_points_off_hides_public_leaderboard(client, officer_headers, soda_id):
    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"points": False}}, headers=officer_headers)
    assert client.get("/api/public/soda/leaderboard").status_code == 404
    assert client.get("/api/public/soda/users").status_code == 200


def test_settings_update_keeps_module_switches(client, officer_headers, soda_id):
    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"calendar": False}}, headers=officer_headers)
    client.put(f"/api/organizations/{soda_id}/settings", json={"config": {"theme": "dark"}}, headers=officer_headers)
    modules = client.get(f"/api/organizations/{soda_id}/modules", headers=officer_headers).get_json()["modules"]
    assert {m["name"]: m["enabled"] for m in modules}["calendar"] is False


@pytest.mark.parametrize(
    "body", [{}, {"modules": {"auth": False}}, {"modules": {"points": "no"}}, {"modules": {"nope": True}}]
)
def test_bad_module_changes_are_refused(client, officer_headers, soda_id, body):
    response = client.put(f"/api/organizations/{soda_id}/modules", json=body, headers=officer_headers)
    assert response.status_code == 400


def test_module_routes_need_officer(client, soda_id):
    assert client.get(f"/api/organizations/{soda_id}/modules").status_code == 401
