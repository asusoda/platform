"""Dashboard notifications: current problems, resolve and reopen."""

import uuid

import pytest

BASE = "/api/dashboard/ais/notifications"


@pytest.fixture
def failing_source(app):
    from core.db import db_connect
    from modules.knowledge.models import KnowledgeSource
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    org_id = db.query(Organization.id).filter_by(prefix="ais").scalar()
    key = "notice-" + uuid.uuid4().hex[:8]
    source = KnowledgeSource(
        organization_id=org_id, key=key, url="https://example.invalid/", category="x", fetch_every_hours=24
    )
    source.last_error = "example.invalid does not resolve"
    db.add(source)
    db.commit()
    yield db, source
    db.delete(source)
    db.commit()
    db.close()


def _mine(body, key):
    return [n for n in body["notifications"] if n["subject"] == key]


def test_resolve_and_reopen(client, officer_headers, failing_source):
    db, source = failing_source
    body = client.get(BASE, headers=officer_headers).get_json()
    [notice] = _mine(body, source.key)
    assert notice["module"] == "knowledge" and notice["link"] == "knowledge" and notice["resolved_at"] is None
    before = body["open"]

    resolved = client.post(f"{BASE}/resolve", json={"ids": [notice["id"]]}, headers=officer_headers).get_json()
    [after] = _mine(resolved, source.key)
    assert after["resolved_at"] and after["resolved_by"].startswith("officer")
    assert resolved["open"] == before - 1
    overview = client.get("/api/dashboard/ais/overview", headers=officer_headers).get_json()
    assert all(p["subject"] != source.key for p in overview["problems"])

    source.last_error = "a new error"
    db.commit()
    [changed] = _mine(client.get(BASE, headers=officer_headers).get_json(), source.key)
    assert changed["id"] != notice["id"] and changed["resolved_at"] is None

    client.post(f"{BASE}/resolve", json={"ids": [changed["id"]]}, headers=officer_headers)
    reopened = client.post(f"{BASE}/reopen", json={"ids": [changed["id"]]}, headers=officer_headers).get_json()
    assert _mine(reopened, source.key)[0]["resolved_at"] is None


def test_bad_ids_are_refused(client, officer_headers):
    for bad in ({}, {"ids": []}, {"ids": "x"}, {"ids": [1]}):
        assert client.post(f"{BASE}/resolve", json=bad, headers=officer_headers).status_code == 400, bad


def test_officers_only(client):
    assert client.get(BASE).status_code in (401, 403)


def test_webhook_events_are_notifications(client, officer_headers, sent, monkeypatch):
    from core import webhooks
    from core.db import db_connect

    monkeypatch.setattr(webhooks, "KEEP_COUNT", 2)
    for title in ("first", "second", "third"):
        webhooks.emit("ais", "pod.stopped", webhooks.Message(title=f"pod {title}", fields=(("Pod", "abc"),)))
    webhooks.emit("ais", "errors", webhooks.Message(title="KeyError", text="boom", color=webhooks.RED))
    try:
        body = client.get(BASE, headers=officer_headers).get_json()
        events = [n for n in body["notifications"] if n["kind"] == "event"]
        assert [n["subject"] for n in events] == ["KeyError", "pod third"]
        error, pod = events
        assert error["level"] == "error" and error["link"] == "activity?tab=errors" and error["at"]
        assert pod["level"] == "info" and pod["module"] == "compute" and pod["message"] == "Pod: abc"
        resolved = client.post(f"{BASE}/resolve", json={"ids": [error["id"]]}, headers=officer_headers).get_json()
        assert next(n for n in resolved["notifications"] if n["id"] == error["id"])["resolved_by"]
        assert resolved["open"] == body["open"] - 1
    finally:
        db = db_connect.SessionLocal()
        db.query(webhooks.Notification).delete()
        db.commit()
        db.close()
