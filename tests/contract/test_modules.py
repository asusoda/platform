"""Orgs can turn optional modules off; a turned-off module's org routes return 404."""

from dataclasses import replace

import pytest

from tests.contract.tool_names import every_name


def _soda_id(client, officer_headers):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    return next(o["id"] for o in orgs if o["prefix"] == "soda")


@pytest.fixture
def soda_id(client, officer_headers, restore_soda_config):
    return _soda_id(client, officer_headers)


def test_modules_are_on_by_default(client, officer_headers, soda_id):
    response = client.get(f"/api/organizations/{soda_id}/modules", headers=officer_headers)
    assert response.status_code == 200
    rows = response.get_json()["modules"]
    assert {m["name"]: m["enabled"] for m in rows} == {
        "points": True,
        "calendar": True,
        "godfather": True,
        "feeds": True,
        "uptime": True,
        "knowledge": True,
        "integrations": True,
        "hosting": True,
        "bot.leetcode": True,
        "bot.games": True,
        "points.leaderboard": True,
        "points.checkins": True,
        "points.store": True,
        "knowledge.asu": False,
        "knowledge.web": True,
        "knowledge.asu_signin": True,
        "feeds.jobs": True,
        "feeds.hackathons": True,
    }
    store = next(m for m in rows if m["name"] == "points.store")
    assert store["parent"] == "points" and store["shared"] is False
    asu = next(m for m in rows if m["name"] == "knowledge.asu")
    assert asu["parent"] == "knowledge" and asu["shared"] is True


def test_turned_off_module_returns_404(client, officer_headers, soda_id):
    assert client.get("/api/storefront/soda/products").status_code == 200
    response = client.put(
        f"/api/organizations/{soda_id}/modules", json={"modules": {"points.store": False}}, headers=officer_headers
    )
    assert response.status_code == 200
    assert client.get("/api/storefront/soda/products").status_code == 404
    # Other orgs and other modules are unaffected
    assert client.get("/api/storefront/ais/products").status_code == 200
    assert client.get("/api/public/soda/leaderboard").status_code == 200


def test_a_sub_module_is_off_while_its_module_is_off(client, officer_headers, soda_id):
    switch = f"/api/organizations/{soda_id}/modules"
    response = client.put(switch, json={"modules": {"points": False}}, headers=officer_headers)
    states = {m["name"]: m["enabled"] for m in response.get_json()["modules"]}
    assert states["points.store"] is False and states["points.leaderboard"] is False
    assert client.get("/api/storefront/soda/products").status_code == 404
    response = client.put(switch, json={"modules": {"points": True}}, headers=officer_headers)
    states = {m["name"]: m["enabled"] for m in response.get_json()["modules"]}
    assert states["points.store"] is True
    assert client.get("/api/storefront/soda/products").status_code == 200


def test_points_sub_modules_gate_their_routes(client, officer_headers, soda_id):
    switch = f"/api/organizations/{soda_id}/modules"
    client.put(switch, json={"modules": {"points.leaderboard": False}}, headers=officer_headers)
    assert client.get("/api/points/soda/leaderboard", headers=officer_headers).status_code == 404
    assert client.get("/api/public/soda/leaderboard").status_code == 404
    assert client.get("/api/points/soda/users", headers=officer_headers).status_code == 200
    client.put(switch, json={"modules": {"points.checkins": False}}, headers=officer_headers)
    upload = client.post("/api/points/soda/uploadEventCSV", headers=officer_headers)
    assert upload.status_code == 404


@pytest.mark.parametrize(
    ("legacy", "key"),
    [("storefront", "points.store"), ("runpod", "hosting"), ("leetcode", "bot.leetcode"), ("games", "bot.games")],
)
def test_a_legacy_key_sets_the_new_key(client, officer_headers, soda_id, legacy, key):
    from core.db import db_connect
    from modules.organizations.models import Organization

    response = client.put(
        f"/api/organizations/{soda_id}/modules", json={"modules": {legacy: False}}, headers=officer_headers
    )
    assert response.status_code == 200
    states = {m["name"]: m["enabled"] for m in response.get_json()["modules"]}
    assert legacy not in states and states[key] is False
    db = db_connect.SessionLocal()
    try:
        org = db.get(Organization, soda_id)
        assert org is not None
        saved = (org.config or {})["modules"]
    finally:
        db.close()
    assert legacy not in saved and saved[key] is False


def test_a_sub_module_turned_on_runs_on_enable(app, monkeypatch):
    from core import submodules
    from core.db import db_connect
    from modules.organizations import service
    from modules.organizations.models import Organization

    calls = []
    store = submodules.SUBMODULES["points.store"]
    monkeypatch.setitem(
        submodules.SUBMODULES, "points.store", replace(store, on_enable=lambda db, org_id: calls.append(org_id))
    )
    db = db_connect.SessionLocal()
    try:
        org = db.query(Organization).filter_by(prefix="ais").one()
        service.set_modules(db, org, {"points.store": False})
        service.set_modules(db, org, {"points.store": True})
        service.set_modules(db, org, {"points.store": True})
        assert calls == [org.id]
    finally:
        db.close()


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
    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"feeds": False}}, headers=officer_headers)
    response = client.get("/api/dashboard/soda/modules", headers=officer_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert CORE not in body["categories"]
    found = {m["name"]: m for m in body["modules"]}
    listed = {name for category, names in CATEGORIES.items() if category != CORE for name in names}
    assert set(found) == listed
    assert set(CATALOG) - set(CATEGORIES[CORE]) <= listed
    assert found["feeds"]["enabled"] is False and found["feeds"]["switchable"] is True
    assert found["points"]["enabled"] is True
    assert [s["key"] for s in found["points"]["submodules"]] == [
        "points.leaderboard",
        "points.checkins",
        "points.store",
    ]
    assert all(s["enabled"] for s in found["points"]["submodules"])
    assert found["knowledge"]["switchable"] is True and found["knowledge"]["enabled"] is True
    assert [p["name"] for p in found["knowledge"]["shared_content"]] == ["asu"]
    assert [p["key"] for p in found["feeds"]["shared_content"]] == ["feeds.jobs", "feeds.hackathons"]
    assert [s["key"] for s in found["knowledge"]["submodules"]] == [
        "knowledge.asu",
        "knowledge.web",
        "knowledge.asu_signin",
    ]
    games = found["bot.games"]
    assert games["category"] == "Discord" and games["parent"] == "bot" and games["switchable"] is True
    assert games["needs"] == [
        {"key": "discord", "label": "Discord bot", "kind": "integration", "optional": False, "connected": False}
    ]
    assert games["ready"] is False
    assert [layer["name"] for layer in body["layers"]] == ["hosting"]
    assert body["layers"][0]["category"] is None and body["layers"][0]["switchable"] is True


def test_module_catalog_needs_officer(client):
    assert client.get("/api/dashboard/soda/modules").status_code == 401


def test_integrations_list_the_modules_they_unlock(client, officer_headers):
    body = client.get("/api/dashboard/soda/integrations", headers=officer_headers).get_json()
    unlocks = {i["key"]: i["unlocks"] for i in body["integrations"]}
    assert unlocks["runpod"] == ["Godfather", "Hosting"]
    assert unlocks["notion"] == ["Calendar sync"]


def test_new_org_starts_with_new_org_modules():
    from core import submodules
    from modules.manifest import NEW_ORG_MODULES
    from modules.organizations.service import OPTIONAL_MODULES, new_org_switches

    switches = new_org_switches()
    assert set(switches) == set(OPTIONAL_MODULES) | set(submodules.SUBMODULES)
    assert all(on == (name in NEW_ORG_MODULES) for name, on in switches.items())
    assert not any(switches[key] for key in submodules.SUBMODULES)


def test_catalog_needs_name_real_integrations(app):
    from core.integrations.registry import INTEGRATIONS
    from modules.manifest import CATALOG

    for name, info in CATALOG.items():
        for need in info.needs:
            if need.kind == "integration":
                assert need.key in INTEGRATIONS, f"{name} needs {need.key}, which no module registers"


def test_agent_modules_off_close_their_routes_and_tools(client, officer_headers, soda_id):
    body = {"name": "test-agent", "kind": "agent", "scopes": ["knowledge:read", "org:read"]}
    issued = client.post(f"/api/organizations/{soda_id}/tokens", json=body, headers=officer_headers)
    headers = {"Authorization": f"Bearer {issued.get_json()['token']}"}

    def tools():
        return every_name(client, headers)

    assert client.get("/api/knowledge/sources", headers=headers).status_code == 200
    assert "knowledge.search" in tools()

    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"knowledge": False}}, headers=officer_headers)
    assert client.get("/api/knowledge/sources", headers=headers).status_code == 404
    assert client.get("/api/dashboard/soda/knowledge/sources", headers=officer_headers).status_code == 404
    assert "knowledge.search" not in tools()

    refused = client.put(
        f"/api/organizations/{soda_id}/modules", json={"modules": {"mcp": False}}, headers=officer_headers
    )
    assert refused.status_code == 400


def test_games_follow_the_switch_of_the_officers_org(client, officer_headers, soda_id, restore_soda_config):
    from core.db import db_connect
    from modules.bot.submodules.games import service
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org = db.get(Organization, soda_id)
        assert org is not None
        guild = org.guild_id
        assert service.enabled_for_guilds(db, [guild]) is True
        client.put(
            f"/api/organizations/{soda_id}/modules", json={"modules": {"bot.games": False}}, headers=officer_headers
        )
        db.expire_all()
        assert service.enabled_for_guilds(db, [guild]) is False
        assert service.enabled_for_guilds(db, []) is False
    finally:
        db.close()
