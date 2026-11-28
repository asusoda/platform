"""Tool groups per org, and the guardrail rules at call time: confirm preview, rate classes, MCP annotations."""

import pytest

from tests.contract.tool_names import every_name

BASE = "/api/dashboard/soda/tool-groups"


@pytest.fixture
def token_for(client, officer_headers, restore_soda_config):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    soda_id = next(o["id"] for o in orgs if o["prefix"] == "soda")

    def issue(*scopes):
        body = {"name": "groups-agent", "kind": "agent", "scopes": list(scopes)}
        response = client.post(f"/api/organizations/{soda_id}/tokens", json=body, headers=officer_headers)
        assert response.status_code == 201, response.get_json()
        return {"Authorization": f"Bearer {response.get_json()['token']}"}

    return issue


def _allow(client, officer_headers, groups):
    response = client.put(BASE, json={"groups": groups}, headers=officer_headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_the_listing_names_every_group_with_its_layer(client, officer_headers, restore_soda_config):
    body = client.get(BASE, headers=officer_headers).get_json()
    assert body["allowed"] is None
    groups = {g["key"]: g for g in body["groups"]}
    assert groups["org"]["layer"] == "base" and groups["org"]["tools"] > 0
    assert groups["points"]["layer"] == "module"
    assert groups["github"] == {"key": "github", "layer": "service", "tools": None}


def test_a_group_the_org_does_not_allow_is_hidden_and_404(client, officer_headers, token_for):
    headers = token_for("org:read", "points:read")
    assert client.post("/api/tools/points.leaderboard", json={}, headers=headers).status_code == 200

    assert _allow(client, officer_headers, ["org"])["allowed"] == ["org"]
    names = every_name(client, headers)
    assert "org.info" in names and not any(n.startswith("points.") for n in names)
    assert client.post("/api/tools/points.leaderboard", json={}, headers=headers).status_code == 404
    through_gateway = client.post(
        "/api/tools/modules.call", json={"tool": "points.leaderboard", "arguments": {}}, headers=headers
    )
    assert through_gateway.status_code == 404
    modules = client.post("/api/tools/modules.list", json={}, headers=headers).get_json()["result"]["modules"]
    assert "points" not in {m["name"] for m in modules}

    batch = client.post(
        "/api/tools/batch",
        json={"calls": [{"tool": "org.info"}, {"tool": "points.leaderboard"}]},
        headers=headers,
    ).get_json()["result"]["results"]
    assert [r["status"] for r in batch] == [200, 404]

    _allow(client, officer_headers, None)
    assert client.post("/api/tools/points.leaderboard", json={}, headers=headers).status_code == 200


def test_a_refused_group_is_404_over_mcp_too(client, officer_headers, token_for, app):
    from starlette.testclient import TestClient

    from modules.mcp.server import build_app

    headers = token_for("org:read", "points:read")
    _allow(client, officer_headers, ["org"])
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "points.leaderboard"}}
    with TestClient(build_app(host="testserver")) as mcp:
        reply = mcp.post("/mcp", json=body, headers={**headers, "Accept": "application/json, text/event-stream"})
    result = reply.json()["result"]
    assert result["isError"] is True and "No tool named points.leaderboard" in result["content"][0]["text"]


def test_bad_group_lists_and_machine_tokens_are_refused(client, officer_headers, token_for):
    assert client.put(BASE, json={"groups": ["nope"]}, headers=officer_headers).status_code == 400
    assert client.put(BASE, json={"groups": "org"}, headers=officer_headers).status_code == 400
    machine = token_for("settings:write", "org:read")
    assert client.put(BASE, json={"groups": ["org"]}, headers=machine).status_code in (401, 403)


def test_a_confirm_row_without_confirm_changes_nothing(client, officer_headers, token_for):
    headers = token_for("settings:write", "org:read")
    before = client.get("/api/dashboard/soda/modules", headers=officer_headers).get_json()
    pending = client.post("/api/tools/modules.set", json={"modules": {"points": False}}, headers=headers)
    assert pending.status_code == 200 and pending.get_json()["result"]["confirm_required"] is True
    assert client.get("/api/dashboard/soda/modules", headers=officer_headers).get_json() == before


@pytest.fixture
def clear_tool_counters(app):
    """No tools.* usage from other tests in this minute, before and after."""
    from core.db import db_connect
    from core.limits import UsageCounter

    def clear():
        db = db_connect.SessionLocal()
        try:
            db.query(UsageCounter).filter(UsageCounter.key.like("tools.%")).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    clear()
    yield
    clear()


def test_a_rate_class_limit_returns_429(client, token_for, monkeypatch, clear_tool_counters):
    monkeypatch.setenv("LIMIT_TOOLS_LIVE_PER_MINUTE", "1")
    headers = token_for("integrations:manage")
    first = client.post("/api/tools/connections.test", json={"key": "notion"}, headers=headers)
    assert first.status_code != 429, first.get_json()
    second = client.post("/api/tools/connections.test", json={"key": "notion"}, headers=headers)
    assert second.status_code == 429


def test_mcp_annotations_follow_the_row(client, token_for):
    headers = token_for("secrets:manage")
    listed = {t["name"]: t for t in client.get("/api/tools", headers=headers).get_json()["tools"]}
    assert listed["access.secrets"]["read_only"] is True
    assert listed["access.set_secret"]["read_only"] is False and listed["access.set_secret"]["confirm"] is True
    assert listed["access.secrets"]["group"] == "access" and listed["access.secrets"]["rate"] == "normal"
