"""Officer control of apps and knowledge from the dashboard. No network."""

import uuid

import pytest

from modules.runpod import service as apps

from .test_runpod_apps import MANIFEST, FakeRunPod


@pytest.fixture
def fake(monkeypatch):
    client = FakeRunPod()
    monkeypatch.setattr(apps, "client_for", lambda db, org_id: client)
    return client


@pytest.fixture
def queued(monkeypatch):
    import core.jobs

    calls = []
    monkeypatch.setattr(core.jobs, "defer", lambda name, **kwargs: calls.append((name, kwargs)))
    return calls


def test_officer_registers_deploys_and_deletes_an_app(client, officer_headers, fake):
    name = "app-" + uuid.uuid4().hex[:8]
    base = f"/api/dashboard/ais/apps/{name}"
    assert client.put(base, json={"manifest": MANIFEST}, headers=officer_headers).status_code == 200

    dry = client.post(f"{base}/deploy", json={"tag": "v1", "dry_run": True}, headers=officer_headers)
    assert dry.status_code == 200 and dry.get_json()["request"]["method"] == "POST" and dry.get_json()["tag"] == "v1"
    assert fake.calls == []

    deployed = client.post(f"{base}/deploy", json={"tag": "v1"}, headers=officer_headers)
    assert deployed.status_code == 202
    assert deployed.get_json()["deployment"]["actor"].startswith("officer:")

    detail = client.get(base, headers=officer_headers).get_json()
    assert detail["current_tag"] == "v1" and [d["tag"] for d in detail["deployments"]] == ["v1"]
    assert client.get(f"{base}/pod", headers=officer_headers).get_json()["pod"]["desiredStatus"] == "RUNNING"
    assert name in [
        a["name"] for a in client.get("/api/dashboard/ais/apps", headers=officer_headers).get_json()["apps"]
    ]

    assert client.post(f"{base}/rollback", json={}, headers=officer_headers).status_code == 409
    assert client.delete(base, headers=officer_headers).get_json()["deleted"] is True
    assert client.get(base, headers=officer_headers).status_code == 404


def test_officer_manages_crawls(client, officer_headers, queued):
    key = "site-" + uuid.uuid4().hex[:8]
    base = "/api/dashboard/ais/knowledge"
    body = {"url": "https://example.edu/about", "category": "club", "fetch_every_hours": 12}
    scheduled = client.put(f"{base}/crawls/{key}", json=body, headers=officer_headers)
    assert scheduled.status_code == 200 and scheduled.get_json()["crawl"]["fetch_every_hours"] == 12

    listed = client.get(f"{base}/sources", headers=officer_headers).get_json()
    assert key in [s["key"] for s in listed["sources"]] and listed["can_publish"] is False

    assert client.post(f"{base}/crawls/{key}/run", json={"force": True}, headers=officer_headers).status_code == 202
    assert queued == [
        ("knowledge.crawl_source", {"org_id": queued[0][1]["org_id"], "key": key, "force": True, "org_prefix": "ais"})
    ]
    assert client.post(f"{base}/crawls/nope/run", json={}, headers=officer_headers).status_code == 404

    found = client.post(f"{base}/search", json={"query": "about"}, headers=officer_headers)
    assert found.status_code == 200

    assert client.delete(f"{base}/sources/{key}", headers=officer_headers).get_json() == {"deleted": True}
    assert client.delete(f"{base}/sources/{key}", headers=officer_headers).status_code == 404


def test_officer_syncs_a_source_pack(client, officer_headers, queued):
    from modules.asu.sources import SOURCES

    base = "/api/dashboard/ais/knowledge"
    listed = client.get(f"{base}/packs", headers=officer_headers).get_json()["packs"]
    assert [(p["name"], p["key_prefix"], p["sources"]) for p in listed] == [("asu", "asu/", 0)]

    first = client.post(f"{base}/packs/asu/sync", headers=officer_headers)
    assert first.status_code == 200 and first.get_json()["added"] == len(SOURCES)
    assert queued[-1] == ("knowledge.crawl_due", {})
    assert client.get(f"{base}/packs", headers=officer_headers).get_json()["packs"][0]["sources"] == len(SOURCES)
    assert client.post(f"{base}/packs/asu/sync", headers=officer_headers).get_json()["added"] == 0
    assert client.post(f"{base}/packs/nope/sync", headers=officer_headers).status_code == 404

    keys = [s["key"] for s in client.get(f"{base}/sources", headers=officer_headers).get_json()["sources"]]
    for key in keys:
        if key.startswith("asu/"):
            client.delete(f"{base}/sources/{key}", headers=officer_headers)


def test_control_routes_need_an_officer(client):
    assert client.get("/api/dashboard/ais/apps").status_code == 401
    assert client.put("/api/dashboard/ais/knowledge/crawls/x", json={}).status_code == 401
    assert client.post("/api/dashboard/ais/knowledge/packs/asu/sync").status_code == 401
