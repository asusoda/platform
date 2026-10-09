"""The error log: grouping, resolve and reopen, dashboard reports, Discord alerts and the superadmin view."""

import logging
import uuid

import pytest

from core import error_log
from modules.dashboard import errors
from tests.contract.conftest import OFFICER_DISCORD_ID
from tests.contract.test_access import SUPERADMIN_ID, headers_for

BASE = "/api/dashboard/ais/errors"
WEBHOOK = "https://discord.com/api/webhooks/123/abc-DEF"


@pytest.fixture
def posts(monkeypatch):
    """Discord posts the alert sends, run in the test thread."""
    sent = []

    class Thread:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    class Response:
        status_code = 204

    monkeypatch.setattr(errors.threading, "Thread", Thread)
    monkeypatch.setattr(errors.requests, "post", lambda url, json, timeout: sent.append((url, json)) or Response())
    monkeypatch.setattr(errors, "_sent", [])
    return sent


def _raise(kind: str, org: str | None = "ais") -> None:
    """Log one exception for org from the same line each time, so repeats group together."""
    token = error_log.current_org.set(org)
    try:
        raise RuntimeError(kind)
    except RuntimeError:
        logging.getLogger("tests.error_log").exception("handling %s", kind)
    finally:
        error_log.current_org.reset(token)


def _open(client, officer_headers):
    return client.get(BASE, headers=officer_headers).get_json()


def _mine(body, marker):
    return [e for e in body["errors"] if marker in e["message"]]


def test_errors_group_and_reopen(client, officer_headers):
    marker = uuid.uuid4().hex
    _raise(marker)
    _raise(marker)
    found = _mine(_open(client, officer_headers), marker)
    assert len(found) == 1
    group = found[0]
    assert group["count"] >= 2
    assert group["kind"] == "RuntimeError"
    assert group["location"] == "tests/contract/test_error_log.py:_raise"
    assert "Traceback" in group["stack"]

    resolved = client.post(f"{BASE}/resolve", json={"ids": [group["id"]]}, headers=officer_headers)
    assert resolved.get_json() == {"changed": 1}
    assert not _mine(_open(client, officer_headers), marker)
    _raise(marker)
    assert _mine(_open(client, officer_headers), marker)[0]["resolved_at"] is None


def test_error_line_in_an_except_block_keeps_the_stack(client, officer_headers):
    marker = uuid.uuid4().hex
    token = error_log.current_org.set("ais")
    try:
        try:
            {}[marker]
        except KeyError as e:
            logging.getLogger("tests.error_log").error(f"lookup failed: {e}")
    finally:
        error_log.current_org.reset(token)
    group = _mine(_open(client, officer_headers), marker)[0]
    assert group["kind"] == "KeyError"
    assert "Traceback" in group["stack"]


def test_errors_of_another_org_are_hidden(client, officer_headers):
    marker = uuid.uuid4().hex
    _raise(marker, "soda")
    assert not _mine(_open(client, officer_headers), marker)
    group_id = error_log.list_groups(_db(), org="soda", limit=200)[0]["id"]
    body = client.post(f"{BASE}/resolve", json={"ids": [group_id]}, headers=officer_headers).get_json()
    assert body == {"changed": 0}


def _db():
    from core.db import db_connect

    return db_connect.SessionLocal()


def test_org_id_and_guild_id_map_to_the_prefix(client, officer_headers):
    marker = uuid.uuid4().hex
    _raise(marker, "1002")
    assert _mine(_open(client, officer_headers), marker)[0]["org"] == "ais"


def test_dashboard_report(client, officer_headers):
    marker = uuid.uuid4().hex
    body = {"kind": "ApiError", "message": f"Could not reach the API {marker}", "page": "/ais/compute"}
    assert client.post(f"{BASE}/report", json=body, headers=officer_headers).get_json() == {"recorded": True}
    group = _mine(_open(client, officer_headers), marker)[0]
    assert group["source"] == "browser"
    assert group["route"] == "/ais/compute"
    assert client.post(f"{BASE}/report", json={"kind": 1}, headers=officer_headers).status_code == 400


def test_webhook_alerts_new_errors_once(client, officer_headers, posts, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    assert (
        client.put(f"{BASE}/webhook", json={"url": "https://example.com/x"}, headers=officer_headers).status_code == 400
    )
    saved = client.put(f"{BASE}/webhook", json={"url": WEBHOOK}, headers=officer_headers)
    assert saved.get_json() == {"webhook_set": True}
    assert _open(client, officer_headers)["webhook_set"] is True
    try:
        marker = uuid.uuid4().hex
        _raise(marker)
        _raise(marker)
        mine = [p for p in posts if marker in p[1]["embeds"][0]["description"]]
        assert len(mine) == 1
        assert mine[0][0] == WEBHOOK
        assert mine[0][1]["allowed_mentions"] == {"parse": []}
    finally:
        client.put(f"{BASE}/webhook", json={"url": None}, headers=officer_headers)
    assert _open(client, officer_headers)["webhook_set"] is False


def test_superadmin_sees_every_org(client, monkeypatch, app):
    from core.config import config
    from modules.auth import access
    from tests.contract.test_access import ScopedBot

    marker = uuid.uuid4().hex
    _raise(marker, None)
    access.clear_cache()
    monkeypatch.setattr(app, "discord_directory", ScopedBot())
    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    monkeypatch.setattr(config, "ACCESS_ENFORCE", True)
    try:
        assert client.get("/api/superadmin/errors", headers=headers_for(OFFICER_DISCORD_ID)).status_code == 403
        body = client.get("/api/superadmin/errors", headers=headers_for(SUPERADMIN_ID)).get_json()
        group = next(e for e in body["errors"] if marker in e["message"])
        assert group["org"] is None
        changed = client.post(
            "/api/superadmin/errors/resolve", json={"ids": [group["id"]]}, headers=headers_for(SUPERADMIN_ID)
        )
        assert changed.get_json() == {"changed": 1}
    finally:
        access.clear_cache()


def test_officers_only(client):
    assert client.get(BASE).status_code in (401, 403)
