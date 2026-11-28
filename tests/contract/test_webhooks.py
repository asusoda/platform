"""Alert destinations: the officer routes, the test message, the fan-out of events through the events.deliver job,
the one send path (modules/alerts/delivery.py) and its deliveries log."""

import uuid

import pytest

from core import net, webhooks

BASE = "/api/dashboard/ais/webhooks"
URL = "https://discord.com/api/webhooks/1234567890/secret-TOKEN"
OTHER_URL = "https://discord.com/api/webhooks/1111111111/other-TOKEN"


def _create(client, headers, name="Ops", events=("errors",), url=URL, **body):
    return client.post(BASE, json={"name": name, "url": url, "events": list(events), **body}, headers=headers)


def _ais_id() -> int:
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        return db.query(Organization).filter_by(prefix="ais").one().id
    finally:
        db.close()


def test_listing_names_events_kinds_and_feeds(client, officer_headers, sent):
    body = client.get(BASE, headers=officer_headers).get_json()
    keys = {e["key"] for e in body["events"]}
    expected = {"errors", "job.failed", "pod.started", "pod.stopped", "app.deployed", "order.created"}
    assert expected | {"member.joined", "knowledge.crawl_failed", "monitor.down", "monitor.up"} <= keys
    assert body["kinds"] == [{"key": "discord", "label": "Discord", "example": "https://discord.com/api/webhooks/..."}]
    assert body["webhooks"] == []
    assert body["feeds"] == []
    assert body["secrets_key"] is True


def test_webhook_lifecycle(client, officer_headers, sent):
    created = _create(client, officer_headers, events=["order.created", "errors"])
    assert created.status_code == 201
    hook = created.get_json()
    assert hook["url_hint"] == "discord.com ...7890"
    assert hook["events"] == ["errors", "order.created"]
    assert hook["enabled"] is True
    listing = client.get(BASE, headers=officer_headers)
    assert "secret-TOKEN" not in listing.get_data(as_text=True)
    assert [w["name"] for w in listing.get_json()["webhooks"]] == ["Ops"]

    assert _create(client, officer_headers).status_code == 409
    changed = client.put(
        f"{BASE}/{hook['id']}", json={"enabled": False, "events": ["job.failed"]}, headers=officer_headers
    )
    assert changed.get_json()["enabled"] is False
    assert changed.get_json()["events"] == ["job.failed"]
    moved = client.put(f"{BASE}/{hook['id']}", json={"url": OTHER_URL}, headers=officer_headers)
    assert moved.get_json()["url_hint"] == "discord.com ...1111"

    assert client.delete(f"{BASE}/{hook['id']}", headers=officer_headers).get_json() == {"deleted": True}
    assert client.delete(f"{BASE}/{hook['id']}", headers=officer_headers).status_code == 404


def test_bad_input_is_refused(client, officer_headers, sent, monkeypatch):
    assert _create(client, officer_headers, url="https://example.com/hook").status_code == 400
    assert _create(client, officer_headers, events=["nope"]).status_code == 400
    assert _create(client, officer_headers, events="errors").status_code == 400
    assert _create(client, officer_headers, name="").status_code == 400
    assert _create(client, officer_headers, kind="smoke").status_code == 400

    def private(url):
        raise net.NotPublic("discord.com resolves to a non-public address")

    monkeypatch.setattr(net, "check_public", private)
    assert _create(client, officer_headers).status_code == 400
    monkeypatch.setattr(net, "check_public", lambda url: None)
    monkeypatch.delenv("SECRETS_KEY")
    refused = _create(client, officer_headers)
    assert refused.status_code == 400
    assert "SECRETS_KEY" in refused.get_json()["error"]


def test_webhooks_of_another_org_are_hidden(client, officer_headers, sent):
    hook = _create(client, officer_headers).get_json()
    other = f"/api/dashboard/soda/webhooks/{hook['id']}"
    assert client.put(other, json={"enabled": False}, headers=officer_headers).status_code == 404
    assert client.post(f"{other}/test", headers=officer_headers).status_code == 404
    assert client.get("/api/dashboard/soda/webhooks", headers=officer_headers).get_json()["webhooks"] == []


def test_send_test(client, officer_headers, sent):
    hook = _create(client, officer_headers, events=["errors", "pod.started"]).get_json()
    result = client.post(f"{BASE}/{hook['id']}/test", headers=officer_headers).get_json()
    assert result["ok"] is True
    url, payload = sent[-1]
    assert url == URL
    assert payload["embeds"][0]["title"] == "Test from AI Society"
    assert "Errors, Pods started" in payload["embeds"][0]["description"]
    assert payload["allowed_mentions"] == {"parse": []}

    sent.status = 404
    failed = client.post(f"{BASE}/{hook['id']}/test", headers=officer_headers).get_json()
    assert failed == {"ok": False, "message": "Discord refused the message with status 404"}
    listed = client.get(BASE, headers=officer_headers).get_json()["webhooks"][0]
    assert listed["last_error"] == failed["message"]
    assert "secret-TOKEN" not in failed["message"]


def test_events_go_only_to_webhooks_that_take_them(client, officer_headers, sent):
    _create(client, officer_headers, name="Store", events=["order.created"])
    _create(client, officer_headers, name="Errors", events=["errors"], url=OTHER_URL)
    off = _create(client, officer_headers, name="Off", events=["order.created"]).get_json()
    client.put(f"{BASE}/{off['id']}", json={"enabled": False}, headers=officer_headers)

    webhooks.emit("ais", "order.created", webhooks.Message(title="New store order #1"))
    assert [url for url, _ in sent] == [URL]
    webhooks.emit(_ais_id(), "errors", webhooks.Message(title="RuntimeError"))
    assert [url for url, _ in sent] == [URL, OTHER_URL]
    webhooks.emit("soda", "order.created", webhooks.Message(title="Another org"))
    webhooks.emit("ais", "undeclared.event", webhooks.Message(title="Nothing"))
    assert len(sent) == 2


def test_alerts_is_core_and_a_destination_that_is_off_gets_nothing(client, officer_headers, sent):
    hook = _create(client, officer_headers, events=["order.created"]).get_json()
    switch = f"/api/organizations/{_ais_id()}/modules"
    assert client.put(switch, json={"modules": {"alerts": False}}, headers=officer_headers).status_code == 400

    client.put(f"{BASE}/{hook['id']}", json={"enabled": False}, headers=officer_headers)
    webhooks.emit("ais", "order.created", webhooks.Message(title="New store order #1"))
    assert sent == []

    client.put(f"{BASE}/{hook['id']}", json={"enabled": True}, headers=officer_headers)
    webhooks.emit("ais", "order.created", webhooks.Message(title="New store order #2"))
    assert [url for url, _ in sent] == [URL]


def test_hourly_limit_is_stored_for_each_event(client, officer_headers, sent, monkeypatch):
    from core import limits
    from core.db import db_connect

    monkeypatch.setenv("LIMIT_ALERTS_MESSAGES", "2")
    _create(client, officer_headers, events=["order.created", "errors"])
    for i in range(3):
        webhooks.emit("ais", "order.created", webhooks.Message(title=f"Order {i}"))
    webhooks.emit("ais", "errors", webhooks.Message(title="KeyError"))
    titles = sorted(payload["embeds"][0]["title"] for _, payload in sent)
    assert len(titles) == 3 and titles[0] == "KeyError" and all(t.startswith("Order") for t in titles[1:])
    # The count is in usage_counters, so every process and session sees it
    db = db_connect.SessionLocal()
    try:
        assert limits.used(db, _ais_id(), "alerts.messages") == 2
        assert limits.take(db, _ais_id(), "alerts.messages", sub="order.created") is False
    finally:
        db.close()


def test_failed_job_of_an_org_sends_job_failed(client, officer_headers, sent):
    from core import jobs

    _create(client, officer_headers, events=["job.failed"])

    def broken(org_prefix: str) -> None:
        raise RuntimeError("the source is down")

    entry = jobs.Job(name="tests.broken", func=broken, cron=None, retry=0, audit=False)
    with pytest.raises(RuntimeError):
        jobs._execute(entry, {"org_prefix": "ais"})
    embed = sent[-1][1]["embeds"][0]
    assert embed["title"] == "Job tests.broken failed"
    assert embed["description"] == "RuntimeError: the source is down"

    entry = jobs.Job(name="tests.global", func=lambda: broken("x"), cron=None, retry=0, audit=False)
    with pytest.raises(RuntimeError):
        jobs._execute(entry, {})
    assert len(sent) == 1


def test_failed_crawl_sends_knowledge_crawl_failed(client, officer_headers, sent):
    from core.db import db_connect
    from modules.knowledge import runs
    from modules.knowledge.models import KnowledgeRun

    _create(client, officer_headers, events=["knowledge.crawl_failed"])
    key = f"docs-{uuid.uuid4().hex[:8]}"
    db = db_connect.SessionLocal()
    try:
        runs.record(db, _ais_id(), key, "upload", runs.Timer(), error="bad file")
        runs.record(db, _ais_id(), key, "crawl", runs.Timer(), changed=True, chunks=3)
        runs.record(db, _ais_id(), key, "crawl", runs.Timer(), error="404 Not Found")
        db.rollback()
    finally:
        db.query(KnowledgeRun).filter_by(source_key=key).delete()
        db.commit()
        db.close()
    assert len(sent) == 1
    assert sent[0][1]["embeds"][0]["title"] == f"Crawl of {key} failed"


def test_new_member_sends_member_joined(client, officer_headers, sent):
    from core.db import db_connect
    from modules.members import service as users
    from modules.members.models import User, UserOrganizationMembership

    _create(client, officer_headers, events=["member.joined"])
    username = f"wh{uuid.uuid4().hex[:8]}"
    db = db_connect.SessionLocal()
    try:
        user, ok, _ = users.manage_user_in_organization(db, _ais_id(), {"name": "Webhook Tester", "username": username})
        assert ok and user is not None
        users.manage_user_in_organization(db, _ais_id(), {"name": "Webhook Tester", "username": username})
    finally:
        found = db.query(User).filter_by(username=username).first()
        if found is not None:
            db.query(UserOrganizationMembership).filter_by(user_id=found.id).delete()
            db.delete(found)
        db.commit()
        db.close()
    assert len(sent) == 1
    embed = sent[0][1]["embeds"][0]
    assert embed["title"] == "Webhook Tester joined"
    assert embed["fields"][0]["value"] == username


def test_pod_and_deploy_messages(client, officer_headers, sent):
    from hosting import service as apps
    from hosting.models import App, AppDeployment
    from modules.godfather import base as godfather

    _create(client, officer_headers, events=["pod.started", "pod.stopped", "app.deployed"])
    godfather.announce(_ais_id(), "gpu-1", "pod123", "start", "the session schedule")
    godfather.announce(_ais_id(), "gpu-1", "pod123", "terminate", "an officer or a tool")
    app = App(organization_id=_ais_id(), name="site")
    apps._announce(app, AppDeployment(tag="v2", status="failed", error="The health path did not answer in time"))
    titles = sorted(payload["embeds"][0]["title"] for _, payload in sent)
    assert titles == ["App site deploy failed", "Pod gpu-1 started", "Pod gpu-1 terminated"]


def test_listing_names_alert_feeds(client, officer_headers, sent):
    from core.db import db_connect
    from modules.feeds.models import AlertFeed

    db = db_connect.SessionLocal()
    db.add(AlertFeed(organization_id=_ais_id(), key="webhook-test-feed", kind="hackathons", config={}))
    db.commit()
    try:
        feeds = client.get(BASE, headers=officer_headers).get_json()["feeds"]
        assert feeds[0]["key"] == "webhook-test-feed"
        assert set(feeds[0]) == {"key", "kind", "enabled", "destination_id", "webhook_set", "last_run_at", "last_error"}
    finally:
        db.query(AlertFeed).filter_by(key="webhook-test-feed").delete()
        db.commit()
        db.close()


def test_officers_only(client):
    assert client.get(BASE).status_code in (401, 403)
    assert client.post(BASE, json={}).status_code in (401, 403)


def _deliveries(client, headers, **query) -> dict:
    response = client.get(f"{BASE}/deliveries", query_string=query, headers=headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_a_destination_may_have_no_events(client, officer_headers, sent):
    created = _create(client, officer_headers, name="Feeds only", events=[])
    assert created.status_code == 201 and created.get_json()["events"] == []
    webhooks.emit("ais", "errors", webhooks.Message(title="KeyError"))
    assert sent == []
    result = client.post(f"{BASE}/{created.get_json()['id']}/test", headers=officer_headers).get_json()
    assert result["ok"] is True
    assert sent[-1][1]["embeds"][0]["description"] == "This webhook works. It gets no events."


def test_events_of_a_module_that_is_off_are_kept_and_not_sent(client, officer_headers, sent):
    from core.db import db_connect
    from modules.organizations.models import Organization

    hook = _create(client, officer_headers, events=["order.created", "errors"]).get_json()
    switch = f"/api/organizations/{_ais_id()}/modules"
    assert client.put(switch, json={"modules": {"points.store": False}}, headers=officer_headers).status_code == 200
    try:
        listing = client.get(BASE, headers=officer_headers).get_json()
        assert "order.created" not in {e["key"] for e in listing["events"]}
        # The dashboard sends back the saved list, with the hidden event in it
        saved = client.put(f"{BASE}/{hook['id']}", json={"events": hook["events"]}, headers=officer_headers)
        assert saved.status_code == 200 and saved.get_json()["events"] == ["errors", "order.created"]
        # A list without the hidden event keeps it too: the officer cannot see it
        saved = client.put(f"{BASE}/{hook['id']}", json={"events": ["errors"]}, headers=officer_headers)
        assert saved.get_json()["events"] == ["errors", "order.created"]
        webhooks.emit("ais", "order.created", webhooks.Message(title="New store order #1"))
        assert sent == []
    finally:
        db = db_connect.SessionLocal()
        org = db.query(Organization).filter_by(prefix="ais").one()
        db.close()
        client.put(switch, json={"modules": {"points.store": True}}, headers=officer_headers)
        assert org is not None


def test_every_send_is_logged_on_the_destination_and_in_deliveries(client, officer_headers, sent):
    hook = _create(client, officer_headers, events=["pod.started", "errors"]).get_json()
    webhooks.emit("ais", "pod.started", webhooks.Message(title="Pod gpu-1 started"))
    sent.wait().status = 400
    webhooks.emit("ais", "errors", webhooks.Message(title="KeyError", text="boom"))
    sent.wait()
    listed = client.get(BASE, headers=officer_headers).get_json()["webhooks"][0]
    assert listed["last_sent_at"] is not None
    assert listed["last_error"] == "Discord refused the message with status 400"

    page = _deliveries(client, officer_headers)
    assert [(d["source"], d["ref"], d["status"], d["destination_id"]) for d in page["deliveries"]] == [
        ("event", "errors", "failed", hook["id"]),
        ("event", "pod.started", "sent", hook["id"]),
    ]
    assert page["deliveries"][0]["error"] == "Discord refused the message with status 400"
    assert page["next"] is None
    assert [d["ref"] for d in _deliveries(client, officer_headers, status="sent")["deliveries"]] == ["pod.started"]
    first = _deliveries(client, officer_headers, limit=1)
    assert len(first["deliveries"]) == 1 and first["next"] == first["deliveries"][0]["id"]
    rest = _deliveries(client, officer_headers, before=first["next"])
    assert [d["ref"] for d in rest["deliveries"]] == ["pod.started"]
    assert client.get(f"{BASE}/deliveries?source=nope", headers=officer_headers).status_code == 400
    assert client.get(f"{BASE}/deliveries?limit=x", headers=officer_headers).status_code == 400
    assert client.get("/api/dashboard/soda/webhooks/deliveries", headers=officer_headers).get_json() == {
        "deliveries": [],
        "next": None,
    }


def test_the_send_path_waits_once_on_429_and_follows_no_redirect(client, officer_headers, sent):
    hook = _create(client, officer_headers, events=["errors"]).get_json()
    sent.statuses = [429, 204]
    webhooks.emit("ais", "errors", webhooks.Message(title="KeyError"))
    assert (
        len(sent) == 2
        and _deliveries(client, officer_headers)["deliveries"][0]["status"] == "sent"
        and all(kwargs["allow_redirects"] is False for kwargs in sent.kwargs)
    )
    sent.statuses = [429, 429]
    result = client.post(f"{BASE}/{hook['id']}/test", headers=officer_headers).get_json()
    assert result == {"ok": False, "message": "Discord rate limited the message twice (status 429)"}
    sent.statuses = [301]
    result = client.post(f"{BASE}/{hook['id']}/test", headers=officer_headers).get_json()
    assert result == {"ok": False, "message": "Discord refused the message with status 301"}


def test_a_host_that_is_not_public_at_send_time_gets_nothing(client, officer_headers, sent, monkeypatch):
    hook = _create(client, officer_headers, events=["errors"]).get_json()

    def private(url, json, **kwargs):
        raise net.NotPublic("discord.com resolves to a non-public address")

    monkeypatch.setattr(net, "post", private)
    result = client.post(f"{BASE}/{hook['id']}/test", headers=officer_headers).get_json()
    assert result == {"ok": False, "message": "The Discord host is not a public address"}


def test_discord_bodies_leave_out_empty_keys_and_fit_the_limits():
    from modules.alerts import delivery

    from .conftest import discord_problems

    bare = delivery.KINDS["discord"].format(webhooks.Message(title="Pod gpu-1 started"))
    assert bare["embeds"][0] == {"title": "Pod gpu-1 started", "color": webhooks.BLUE}
    huge = webhooks.Message(
        title="t" * 300,
        text="d" * 5000,
        fields=tuple((f"name {i}", "v" * 1100) for i in range(30)) + (("", ""),),
        footer="f" * 3000,
        timestamp="2026-10-08T12:00:00Z",
    )
    body = delivery.KINDS["discord"].format(huge)
    assert discord_problems(body) == []
    embed = body["embeds"][0]
    assert len(embed["title"]) == 256 and len(embed["fields"]) <= 25
