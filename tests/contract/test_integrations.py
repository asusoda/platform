"""Dashboard integrations: status, saving keys, and tests with no network."""

import json

import pytest

BASE = "/api/dashboard/ais/integrations"


@pytest.fixture
def cleared(client, officer_headers, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    yield
    client.put(f"{BASE}/notion", json={"fields": {"notion_api_key": None}}, headers=officer_headers)
    client.put(f"{BASE}/google", json={"fields": {"google_service_account": None}}, headers=officer_headers)
    for key, names in (
        ("embeddings", ("embeddings_url", "embeddings_model", "embeddings_api_key", "embeddings_query_prefix")),
        ("firecrawl", ("firecrawl_url", "firecrawl_api_key")),
        ("searxng", ("searxng_url", "searxng_engines")),
    ):
        client.put(f"{BASE}/{key}", json={"fields": dict.fromkeys(names)}, headers=officer_headers)


@pytest.fixture
def public_dns(monkeypatch):
    """Every host resolves to a public address, or to 10.0.0.5 when its name starts with internal."""
    import socket

    def resolve(host, port):
        address = "10.0.0.5" if host.startswith("internal") else "93.184.216.34"
        return [(socket.AF_INET, 0, 0, "", (address, port))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)


def _by_key(body):
    return {i["key"]: i for i in body["integrations"]}


def test_lists_every_integration(client, officer_headers):
    body = client.get(BASE, headers=officer_headers).get_json()
    found = _by_key(body)
    assert {"discord", "embeddings", "github", "google", "notion", "runpod"} <= set(found)
    assert found["notion"]["used_by"] == ["calendar"]
    assert set(found["runpod"]["used_by"]) == {"compute", "runpod"}
    assert found["discord"]["editable"] is False and found["discord"]["fields"] == []
    assert found["embeddings"]["source"] is None


def test_save_and_clear_keys(client, officer_headers, cleared):
    saved = client.put(f"{BASE}/notion", json={"fields": {"notion_api_key": "secret_abc"}}, headers=officer_headers)
    assert saved.status_code == 200
    notion = _by_key(saved.get_json())["notion"]
    assert notion["source"] == "org" and notion["fields"][0]["set"] is True
    assert "secret_abc" not in saved.get_data(as_text=True)

    cleared = client.put(f"{BASE}/notion", json={"fields": {"notion_api_key": None}}, headers=officer_headers)
    assert _by_key(cleared.get_json())["notion"]["fields"][0]["set"] is False


def test_bad_saves_are_refused(client, officer_headers, cleared):
    for key, body in (
        ("notion", {}),
        ("notion", {"fields": {"other": "x"}}),
        ("discord", {"fields": {"x": "y"}}),
        ("nope", {"fields": {"x": "y"}}),
        ("google", {"fields": {"google_service_account": "not json"}}),
        ("google", {"fields": {"google_service_account": json.dumps([1])}}),
    ):
        assert client.put(f"{BASE}/{key}", json=body, headers=officer_headers).status_code == 400, (key, body)


def test_failed_test_says_why(client, officer_headers, monkeypatch):
    monkeypatch.delenv("EMBEDDINGS_URL", raising=False)
    result = client.post(f"{BASE}/embeddings/test", headers=officer_headers).get_json()
    assert result == {"ok": False, "message": "Set an embeddings service first"}
    assert client.post(f"{BASE}/github/test", headers=officer_headers).get_json()["ok"] is False


def test_officers_only(client):
    assert client.get(BASE).status_code in (401, 403)


def _org_id(name="ais"):
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        return db.query(Organization).filter_by(prefix=name).one().id
    finally:
        db.close()


def test_org_embeddings_replace_the_deployment_default(client, officer_headers, cleared, public_dns, monkeypatch):
    from core.db import db_connect
    from modules.knowledge import embedder

    monkeypatch.setenv("EMBEDDINGS_URL", "http://llama-embed:8080/v1")
    monkeypatch.setenv("EMBEDDINGS_MODEL", "deployment-model")
    half = client.put(
        f"{BASE}/embeddings", json={"fields": {"embeddings_url": "https://e.example/v1"}}, headers=officer_headers
    )
    assert half.status_code == 400 and "Model" in half.get_json()["error"]
    private = {"embeddings_url": "https://internal.example/v1", "embeddings_model": "m"}
    assert client.put(f"{BASE}/embeddings", json={"fields": private}, headers=officer_headers).status_code == 400

    fields = {"embeddings_url": "https://e.example/v1", "embeddings_model": "org-model"}
    saved = client.put(f"{BASE}/embeddings", json={"fields": fields}, headers=officer_headers)
    assert saved.status_code == 200
    entry = _by_key(saved.get_json())["embeddings"]
    assert entry["source"] == "org"
    shown = {f["name"]: f["value"] for f in entry["fields"]}
    assert shown["embeddings_url"] == "https://e.example/v1" and shown["embeddings_api_key"] is None

    db = db_connect.SessionLocal()
    try:
        own = embedder.for_org(db, _org_id())
        other = embedder.for_org(db, _org_id("soda"))
    finally:
        db.close()
    assert own is not None and own.model == "org-model" and own.public_only
    assert other is not None and other.model == "deployment-model" and not other.public_only


def test_org_firecrawl_and_searxng(client, officer_headers, cleared, public_dns, monkeypatch):
    from core.db import db_connect
    from modules.asu import settings
    from modules.knowledge import fetch

    monkeypatch.delenv("FIRECRAWL_URL", raising=False)
    monkeypatch.setenv("SEARXNG_URL", "http://searxng:8080")
    client.put(f"{BASE}/firecrawl", json={"fields": {"firecrawl_url": "https://fc.example"}}, headers=officer_headers)
    client.put(f"{BASE}/searxng", json={"fields": {"searxng_url": "https://s.example"}}, headers=officer_headers)
    db = db_connect.SessionLocal()
    try:
        assert fetch.firecrawl_for(db, _org_id()) == fetch.Firecrawl("https://fc.example", None, public_only=True)
        assert fetch.firecrawl_for(db, _org_id("soda")) is None
        with settings.query_scope(db, _org_id()):
            search = settings.settings().search
            assert search.base_url == "https://s.example" and search.engines == settings.DEFAULT_ENGINES
        assert settings.settings().search.base_url == "http://searxng:8080"
    finally:
        db.close()
