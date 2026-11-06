"""An app's own MCP server through Platform: an existing pod adopted, its address, and the proxied calls."""

import pytest

from modules.runpod import app_mcp, service

from .test_runpod_apps import MANIFEST, FakeRunPod, _issue, _name


@pytest.fixture
def fake(monkeypatch):
    client = FakeRunPod()
    monkeypatch.setattr(service, "client_for", lambda db, org_id, provider="runpod": client)
    return client


@pytest.fixture
def manager(app):
    return _issue("ais", "apps:read", "apps:manage")


WITH_MCP = MANIFEST | {"mcp": {"port": 6006, "path": "/mcp", "token_secret": "app_tracing_key"}}


def test_an_app_adopts_a_pod_and_its_mcp_address_is_the_pod_proxy(client, manager, fake):
    name = _name()
    body = {"manifest": WITH_MCP, "pod_id": "8pgxxcyb1slrc6"}
    response = client.put(f"/api/apps/{name}", json=body, headers=manager)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["pod_id"] == "8pgxxcyb1slrc6"

    from core.db import db_connect
    from modules.runpod.service import _find

    db = db_connect.SessionLocal()
    try:
        org_id = _find_org(db)
        assert app_mcp.endpoint(_find(db, org_id, name)) == "https://8pgxxcyb1slrc6-6006.proxy.runpod.net/mcp"
    finally:
        db.close()


def _find_org(db):
    from modules.organizations.models import Organization

    return db.query(Organization.id).filter_by(prefix="ais").scalar()


def test_a_bad_pod_id_is_refused(client, manager, fake):
    response = client.put(f"/api/apps/{_name()}", json={"manifest": MANIFEST, "pod_id": "../x"}, headers=manager)
    assert response.status_code == 400


def test_an_app_without_mcp_says_so(client, manager, fake):
    name = _name()
    client.put(f"/api/apps/{name}", json={"manifest": MANIFEST}, headers=manager)
    response = client.post("/api/tools/hosting.mcp_tools", json={"name": name}, headers=manager)
    assert response.status_code == 404 and "mcp" in response.get_json()["error"]


def test_tools_are_listed_and_called_with_the_app_token(client, manager, fake, monkeypatch):
    name = _name()
    client.put(f"/api/apps/{name}", json={"manifest": WITH_MCP, "pod_id": "8pgxxcyb1slrc6"}, headers=manager)
    from core import secrets

    monkeypatch.setattr(secrets, "get_secret", lambda db, org_id, key: "px-key" if key == "app_tracing_key" else None)
    monkeypatch.setattr(app_mcp.net, "check_public", lambda url: None)
    seen = {}

    async def session(url, token, work):
        seen.update(url=url, token=token)

        class Listed:
            tools = [type("T", (), {"name": "list_projects", "description": "Projects", "input_schema": {}})()]

        class Called:
            content = [type("C", (), {"text": "default"})()]
            structured_content = None
            is_error = False

        class Session:
            async def list_tools(self):
                return Listed()

            async def call_tool(self, tool, arguments):
                seen.update(tool=tool, arguments=arguments)
                return Called()

        return await work(Session())

    monkeypatch.setattr(app_mcp, "_session", session)
    listed = client.post("/api/tools/hosting.mcp_tools", json={"name": name}, headers=manager).get_json()
    assert listed["result"]["tools"][0]["name"] == "list_projects"
    called = client.post(
        "/api/tools/hosting.mcp_call", json={"name": name, "tool": "list_projects", "arguments": {}}, headers=manager
    ).get_json()
    assert called["result"] == {"text": "default", "structured": None, "is_error": False}
    assert seen == {
        "url": "https://8pgxxcyb1slrc6-6006.proxy.runpod.net/mcp",
        "token": "px-key",
        "tool": "list_projects",
        "arguments": {},
    }


@pytest.mark.parametrize("mcp", [{}, {"url": "http://x.test/mcp"}, {"port": 0}, {"port": 1, "extra": 1}])
def test_bad_mcp_manifests_are_refused(client, manager, mcp):
    response = client.put(f"/api/apps/{_name()}", json={"manifest": MANIFEST | {"mcp": mcp}}, headers=manager)
    assert response.status_code == 400
