"""The layered tool list: base and service tools at the top, module tools behind the modules gateway."""

import pytest


@pytest.fixture
def token_for(client, officer_headers, restore_soda_config):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    soda_id = next(o["id"] for o in orgs if o["prefix"] == "soda")

    def issue(*scopes):
        body = {"name": "test-agent", "kind": "agent", "scopes": list(scopes)}
        response = client.post(f"/api/organizations/{soda_id}/tokens", json=body, headers=officer_headers)
        assert response.status_code == 201, response.get_json()
        return {"Authorization": f"Bearer {response.get_json()['token']}"}

    return issue


def _call(client, headers, tool, /, **arguments):
    return client.post(f"/api/tools/{tool}", json=arguments, headers=headers)


def _listed(client, headers):
    return [t["name"] for t in client.get("/api/tools", headers=headers).get_json()["tools"]]


def test_the_list_holds_base_tools_and_gateways(client, token_for):
    headers = token_for("org:read", "points:read")
    assert _listed(client, headers) == [
        "batch",
        "modules.call",
        "modules.list",
        "modules.skill",
        "modules.tools",
        "org.branding",
        "org.info",
        "org.limits",
        "org.settings",
    ]


def test_no_gateway_without_tools_behind_it(client, token_for):
    assert _listed(client, token_for("activity:read")) == [
        "activity.ci_runs",
        "activity.errors",
        "activity.log",
        "activity.notifications",
        "batch",
        "org.overview",
        "org.trends",
    ]


def test_modules_list_skill_tools_and_call(client, token_for):
    headers = token_for("points:read")
    modules = _call(client, headers, "modules.list").get_json()["result"]["modules"]
    assert modules == [
        {"name": "points", "tools": 1, "description": "Points, leaderboards and event check-ins.", "skill": True}
    ]
    skill = _call(client, headers, "modules.skill", name="points").get_json()["result"]
    assert skill["skill"].startswith("---\nname: points")
    tools = _call(client, headers, "modules.tools", name="points").get_json()["result"]["tools"]
    assert [t["name"] for t in tools] == ["points.leaderboard"]
    called = _call(client, headers, "modules.call", tool="points.leaderboard", arguments={"limit": 3})
    assert called.status_code == 200
    assert "leaderboard" in called.get_json()["result"]
    # The same tool also runs by its own name
    assert _call(client, headers, "points.leaderboard", limit=3).status_code == 200


def test_the_gateway_runs_only_module_tools(client, token_for):
    headers = token_for("org:read", "points:read")
    base = _call(client, headers, "modules.call", tool="org.info")
    assert base.status_code == 400 and "the tool list" in base.get_json()["error"]
    service = _call(client, headers, "modules.call", tool="github.list_issues")
    assert service.status_code == 400 and "the tool list" in service.get_json()["error"]
    assert _call(client, headers, "modules.call", tool="batch").status_code == 400
    assert _call(client, headers, "modules.call", tool="modules.call").status_code == 400


def test_a_gateway_hides_what_the_token_cannot_use(client, token_for):
    headers = token_for("org:read")
    assert _call(client, headers, "modules.tools", name="points").status_code == 404
    assert _call(client, headers, "modules.skill", name="points").status_code == 404
    assert _call(client, headers, "modules.call", tool="points.leaderboard").status_code == 404
    assert _call(client, headers, "modules.call", tool="nothing.here").status_code == 404


def test_the_inner_call_is_audited(client, token_for):
    from core.audit import AuditEntry
    from core.db import db_connect

    headers = token_for("points:read")
    _call(client, headers, "modules.call", tool="points.leaderboard", arguments={})
    db = db_connect.SessionLocal()
    try:
        actions = [e.action for e in db.query(AuditEntry).order_by(AuditEntry.id.desc()).limit(2)]
    finally:
        db.close()
    assert actions == ["tool modules.call", "tool points.leaderboard"]
