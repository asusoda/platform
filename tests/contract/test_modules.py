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
        "leetcode": True,
        "compute": True,
        "alerts": True,
        "uptime": True,
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


def test_module_catalog_lists_every_module_but_core(client, officer_headers, soda_id, monkeypatch):
    from modules.manifest import CATALOG, CATEGORIES, CORE

    monkeypatch.delenv("BOT_TOKEN", raising=False)
    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"alerts": False}}, headers=officer_headers)
    response = client.get("/api/dashboard/soda/modules", headers=officer_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert CORE not in body["categories"]
    found = {m["name"]: m for m in body["modules"]}
    assert set(found) == set(CATALOG) - set(CATEGORIES[CORE])
    assert found["alerts"]["enabled"] is False and found["alerts"]["switchable"] is True
    assert found["points"]["enabled"] is True
    assert found["knowledge"]["switchable"] is False and found["knowledge"]["enabled"] is True
    assert [p["name"] for p in found["knowledge"]["packs"]] == ["asu"]
    assert [p["name"] for p in found["alerts"]["packs"]] == ["careers"]
    games = found["games"]
    assert games["needs"] == [
        {"key": "discord", "label": "Discord bot", "kind": "integration", "optional": False, "connected": False}
    ]
    assert games["ready"] is False


def test_module_catalog_needs_officer(client):
    assert client.get("/api/dashboard/soda/modules").status_code == 401


def test_integrations_list_the_modules_they_unlock(client, officer_headers):
    body = client.get("/api/dashboard/soda/integrations", headers=officer_headers).get_json()
    unlocks = {i["key"]: i["unlocks"] for i in body["integrations"]}
    assert unlocks["runpod"] == ["Hosting", "Member pods"]
    assert unlocks["notion"] == ["Calendar sync"]


def test_new_org_starts_with_new_org_modules():
    from modules.manifest import NEW_ORG_MODULES
    from modules.organizations.service import OPTIONAL_MODULES, new_org_switches
    from modules.superadmin.service import new_organization

    switches = new_org_switches()
    assert set(switches) == set(OPTIONAL_MODULES)
    assert all(on == (name in NEW_ORG_MODULES) for name, on in switches.items())
    org = new_organization({"id": "4242", "name": "New Club", "icon_url": None})
    assert org.config["modules"] == switches


def test_catalog_needs_name_real_integrations(app):
    from core.integrations.registry import INTEGRATIONS
    from modules.manifest import CATALOG

    for name, info in CATALOG.items():
        for need in info.needs:
            if need.kind == "integration":
                assert need.key in INTEGRATIONS, f"{name} needs {need.key}, which no module registers"
