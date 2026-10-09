"""Sentry issues on the dashboard and the errors.list tool, with no network."""

import pytest

from core.integrations import sentry
from modules.dashboard import errors

BASE = "/api/dashboard/ais"
FIELDS = ("sentry_auth_token", "sentry_org", "sentry_project", "sentry_url")


class _Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


@pytest.fixture
def connected(client, officer_headers, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    errors.clear_cache()
    saved = client.put(
        f"{BASE}/integrations/sentry",
        json={
            "fields": {"sentry_auth_token": "sntrys_secret_value", "sentry_org": "ais", "sentry_project": "platform"}
        },
        headers=officer_headers,
    )
    assert saved.status_code == 200, saved.get_json()
    yield
    client.put(f"{BASE}/integrations/sentry", json={"fields": dict.fromkeys(FIELDS)}, headers=officer_headers)
    errors.clear_cache()


def _fake(monkeypatch, status_code, body, calls=None):
    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append({"url": url, "params": params, "auth": (headers or {}).get("Authorization")})
        return _Response(status_code, body)

    monkeypatch.setattr(sentry.requests, "get", get)


ISSUE = {
    "id": "1",
    "shortId": "PLATFORM-1",
    "title": "KeyError: pod_id",
    "culprit": "modules.compute.service in create_pod",
    "level": "error",
    "count": "12",
    "userCount": 3,
    "firstSeen": "2026-10-08T01:00:00Z",
    "lastSeen": "2026-10-09T02:45:00Z",
    "permalink": "https://ais.sentry.io/issues/1/",
}


def test_not_connected(client, officer_headers):
    errors.clear_cache()
    body = client.get(f"{BASE}/errors", headers=officer_headers).get_json()
    assert body == {"configured": False, "issues": [], "error": None, "project_url": None}


def test_lists_unresolved_issues(client, officer_headers, connected, monkeypatch):
    calls = []
    _fake(monkeypatch, 200, [ISSUE], calls)
    body = client.get(f"{BASE}/errors?limit=10", headers=officer_headers).get_json()
    assert body["configured"] is True and body["error"] is None
    assert body["issues"][0]["short_id"] == "PLATFORM-1"
    assert body["issues"][0]["count"] == 12
    assert calls[0]["url"] == "https://sentry.io/api/0/projects/ais/platform/issues/"
    assert calls[0]["params"]["query"] == "is:unresolved"
    assert calls[0]["auth"] == "Bearer sntrys_secret_value"
    # A second read within the cache time does not call Sentry
    client.get(f"{BASE}/errors?limit=10", headers=officer_headers)
    assert len(calls) == 1


def test_refused_token_says_why(client, officer_headers, connected, monkeypatch):
    _fake(monkeypatch, 401, {})
    body = client.get(f"{BASE}/errors", headers=officer_headers).get_json()
    assert body["issues"] == []
    assert "refused the token" in body["error"]
    assert "sntrys_secret_value" not in body["error"]


def test_integration_test_names_the_project(client, officer_headers, connected, monkeypatch):
    _fake(monkeypatch, 200, {"name": "platform"})
    body = client.post(f"{BASE}/integrations/sentry/test", headers=officer_headers).get_json()
    assert body == {"ok": True, "message": "Connected to project platform."}


def test_token_is_never_returned(client, officer_headers, connected):
    body = client.get(f"{BASE}/integrations", headers=officer_headers).get_json()
    card = next(i for i in body["integrations"] if i["key"] == "sentry")
    values = {f["name"]: f["value"] for f in card["fields"]}
    assert values["sentry_auth_token"] is None
    assert values["sentry_org"] == "ais"
    assert card["source"] == "org"


def test_officers_only(client):
    assert client.get(f"{BASE}/errors").status_code in (401, 403)
