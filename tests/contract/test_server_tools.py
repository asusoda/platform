"""The server.* tools: only a token made by a superadmin may call them, and server.run names a policy command."""

import pytest

from core.integrations import server as runner

from .test_access import SUPERADMIN_ID, headers_for


@pytest.fixture
def superadmin(monkeypatch):
    from core.config import config

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    return headers_for(SUPERADMIN_ID)


def _soda(client, headers):
    orgs = client.get("/api/organizations/", headers=headers).get_json()
    return next(o["id"] for o in orgs if o["prefix"] == "soda")


def _token(client, headers, scopes):
    org_id = _soda(client, headers)
    body = {"name": "ops", "kind": "app", "scopes": scopes}
    made = client.post(f"/api/organizations/{org_id}/tokens", json=body, headers=headers)
    assert made.status_code == 201, made.get_json()
    return {"Authorization": f"Bearer {made.get_json()['token']}"}


def test_an_officer_token_cannot_use_the_server_tools(client, officer_headers, superadmin):
    headers = _token(client, officer_headers, ["server:read"])
    refused = client.post("/api/tools/server.status", json={}, headers=headers)
    assert refused.status_code == 403


def test_a_superadmin_token_reads_status_and_runs_named_commands(client, superadmin, monkeypatch):
    sent = []

    def call(method, path, body=None, socket_path=None):
        sent.append((method, path))
        if path == "/host/commands":
            return {"commands": [{"name": "health", "description": "Check the containers"}]}
        return {
            "name": "health",
            "exit_code": 0,
            "timed_out": False,
            "seconds": 1.0,
            "output": "ok",
            "truncated": False,
        }

    monkeypatch.setattr(runner, "call", call)
    headers = _token(client, superadmin, ["server:read", "server:manage"])
    status = client.post("/api/tools/server.status", json={}, headers=headers)
    assert status.status_code == 200, status.get_json()
    listed = client.post("/api/tools/server.commands", json={}, headers=headers).get_json()["result"]
    assert listed["commands"][0]["name"] == "health"
    preview = client.post("/api/tools/server.run", json={"name": "health"}, headers=headers).get_json()["result"]
    assert preview["confirm_required"] is True
    assert ("POST", "/host/commands/health") not in sent
    ran = client.post("/api/tools/server.run", json={"name": "health", "confirm": True}, headers=headers)
    assert ran.status_code == 200 and ran.get_json()["result"]["exit_code"] == 0
    assert ("POST", "/host/commands/health") in sent
    bad = client.post("/api/tools/server.run", json={"name": "rm -rf /", "confirm": True}, headers=headers)
    assert bad.status_code == 400


def test_the_shell_needs_confirm_and_is_audited(client, superadmin, monkeypatch):
    from core.audit import AuditEntry
    from core.db import db_connect

    sent: list[tuple] = []

    def call(method, path, body=None, socket_path=None):
        sent.append((method, path, body or {}))
        return {"user": "agent", "exit_code": 0, "timed_out": False, "seconds": 0.1, "output": "x", "truncated": False}

    monkeypatch.setattr(runner, "call", call)
    officer = _token(client, superadmin, ["server:read"])
    assert client.post("/api/tools/server.shell", json={"command": "ls"}, headers=officer).status_code in (403, 404)
    headers = _token(client, superadmin, ["server:manage"])
    preview = client.post("/api/tools/server.shell", json={"command": "ls /srv"}, headers=headers).get_json()
    assert preview["result"]["confirm_required"] is True and not sent
    ran = client.post("/api/tools/server.shell", json={"command": "ls /srv", "confirm": True}, headers=headers)
    assert ran.status_code == 200 and ran.get_json()["result"]["user"] == "agent"
    assert sent[0][:2] == ("POST", "/host/shell") and sent[0][2]["command"] == "ls /srv"
    db = db_connect.SessionLocal()
    try:
        entry = db.query(AuditEntry).filter_by(action="server.shell").order_by(AuditEntry.id.desc()).first()
        details = entry.details if entry is not None else None
        assert isinstance(details, dict) and details["command"] == "ls /srv"
    finally:
        db.close()
