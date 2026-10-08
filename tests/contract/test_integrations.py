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
    assert result == {"ok": False, "message": "EMBEDDINGS_URL is not set on the API"}
    assert client.post(f"{BASE}/github/test", headers=officer_headers).get_json()["ok"] is False


def test_officers_only(client):
    assert client.get(BASE).status_code in (401, 403)
