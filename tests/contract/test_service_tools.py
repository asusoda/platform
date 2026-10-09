"""Google, Notion and web tools: shown only when the org connected the service, and calls reach the service."""

import base64
import json

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from modules.integrations import google, notion, web

NOTION_KEY = "ntn_test_value"


def _service_account() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return json.dumps(
        {
            "type": "service_account",
            "client_email": "agent@test.iam.gserviceaccount.com",
            "private_key": pem,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )


class Answer:
    def __init__(self, body: dict | None = None, status: int = 200, content: bytes = b""):
        self.status_code = status
        self.body = body or {}
        self.content = content
        self.text = json.dumps(self.body)

    def json(self):
        return self.body


class FakeSession:
    """Answers Google API requests from a table of URL endings and records each request."""

    def __init__(self, answers: dict[str, Answer], calls: list):
        self.answers = answers
        self.calls = calls

    def request(self, method, url, timeout, **kwargs):
        self.calls.append((method, url, kwargs))
        for ending, answer in self.answers.items():
            if url.endswith(ending):
                return answer
        return Answer({"error": {"message": "nope"}}, status=404)


@pytest.fixture
def orgs(client, officer_headers, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    listed = client.get("/api/organizations/", headers=officer_headers).get_json()
    return {o["prefix"]: o["id"] for o in listed}


def _save(client, officer_headers, key, fields):
    saved = client.put(f"/api/dashboard/soda/integrations/{key}", json={"fields": fields}, headers=officer_headers)
    assert saved.status_code == 200, saved.get_json()


@pytest.fixture
def connected(client, officer_headers, orgs):
    _save(client, officer_headers, "google", {"google_service_account": _service_account()})
    _save(client, officer_headers, "notion", {"notion_api_key": NOTION_KEY})
    yield orgs["soda"]
    _save(client, officer_headers, "google", {"google_service_account": None, "google_subject": None})
    _save(client, officer_headers, "notion", {"notion_api_key": None})


def _token(client, officer_headers, org_id, scopes):
    body = {"name": "helper", "kind": "agent", "scopes": scopes}
    response = client.post(f"/api/organizations/{org_id}/tokens", json=body, headers=officer_headers)
    assert response.status_code == 201, response.get_json()
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def _names(client, headers, prefix):
    tools = client.get("/api/tools", headers=headers).get_json()["tools"]
    return [t["name"] for t in tools if t["name"].startswith(prefix)]


SCOPES = ["google:read", "google:write", "gmail:read", "gmail:send", "notion:read", "notion:write"]


def test_tools_show_only_for_orgs_that_connected_the_service(client, officer_headers, connected, orgs):
    headers = _token(client, officer_headers, connected, SCOPES)
    assert "google.calendar_events" in _names(client, headers, "google.")
    assert _names(client, headers, "google.gmail") == []
    assert _names(client, headers, "notion.") == [
        "notion.create_page",
        "notion.query_database",
        "notion.read_page",
        "notion.search",
    ]
    other = _token(client, officer_headers, orgs["ais"], SCOPES)
    assert _names(client, other, "google.") == [] and _names(client, other, "notion.") == []
    refused = client.post("/api/tools/notion.search", json={"query": "x"}, headers=other)
    assert refused.status_code == 404


def test_gmail_needs_a_workspace_user(client, officer_headers, connected):
    _save(client, officer_headers, "google", {"google_subject": "officer@club.org"})
    headers = _token(client, officer_headers, connected, ["gmail:read"])
    assert _names(client, headers, "google.") == ["google.gmail_read", "google.gmail_search"]


def test_session_acts_as_the_workspace_user(client, officer_headers, connected):
    from core.db import db_connect

    _save(client, officer_headers, "google", {"google_subject": "officer@club.org"})
    db = db_connect.SessionLocal()
    try:
        signed = google.session(db, connected, google.GMAIL_READ)
    finally:
        db.close()
    assert signed.credentials._subject == "officer@club.org"
    assert signed.credentials._scopes == [google.GMAIL_READ]


def test_google_calls_and_confirm(client, officer_headers, connected, monkeypatch):
    calls: list = []
    answers = {
        "/calendars/club%40group.calendar.google.com/events": Answer(
            {"items": [{"id": "e1", "summary": "GBM", "start": {"date": "2026-10-10"}, "htmlLink": "https://x"}]}
        ),
    }
    monkeypatch.setattr(google, "session", lambda db, org_id, scope: FakeSession(answers, calls))
    headers = _token(client, officer_headers, connected, ["google:read", "google:write"])
    listed = client.post(
        "/api/tools/google.calendar_events",
        json={"calendar_id": "club@group.calendar.google.com", "time_min": "2026-10-01"},
        headers=headers,
    )
    assert listed.status_code == 200, listed.get_json()
    assert listed.get_json()["result"]["events"][0]["summary"] == "GBM"
    assert calls[0][2]["params"]["timeMin"] == "2026-10-01T00:00:00Z"
    args = {
        "calendar_id": "club@group.calendar.google.com",
        "summary": "Social",
        "start": "2026-10-20",
        "end": "2026-10-21",
    }
    pending = client.post("/api/tools/google.calendar_create_event", json=args, headers=headers).get_json()["result"]
    assert pending["confirm_required"] is True and len(calls) == 1
    done = client.post("/api/tools/google.calendar_create_event", json={**args, "confirm": True}, headers=headers)
    assert done.status_code == 200
    method, _, kwargs = calls[-1]
    assert method == "POST" and kwargs["json"]["start"] == {"date": "2026-10-20"}
    missing = client.post("/api/tools/google.drive_read", json={"file_id": "gone"}, headers=headers)
    assert missing.status_code == 404


def test_drive_read_exports_google_docs(client, officer_headers, connected, monkeypatch):
    calls: list = []
    answers = {
        "/files/doc1/export": Answer(content=b"Meeting notes"),
        "/files/doc1": Answer({"id": "doc1", "name": "Notes", "mimeType": "application/vnd.google-apps.document"}),
    }
    monkeypatch.setattr(google, "session", lambda db, org_id, scope: FakeSession(answers, calls))
    headers = _token(client, officer_headers, connected, ["google:read"])
    read = client.post("/api/tools/google.drive_read", json={"file_id": "doc1"}, headers=headers).get_json()
    assert read["result"]["text"] == "Meeting notes" and read["result"]["name"] == "Notes"
    assert calls[-1][2]["params"] == {"mimeType": "text/plain"}


def test_gmail_read_decodes_the_text_part():
    data = base64.urlsafe_b64encode(b"Hello club").decode().rstrip("=")
    payload = {"mimeType": "multipart/alternative", "parts": [{"mimeType": "text/plain", "body": {"data": data}}]}
    assert google._plain(payload) == "Hello club"


def test_notion_calls(client, officer_headers, connected, monkeypatch):
    calls: list = []

    def request(method, url, headers, json, params, timeout):
        assert headers["Authorization"] == f"Bearer {NOTION_KEY}"
        calls.append((method, url, json))
        if url.endswith("/search"):
            title = {"type": "title", "title": [{"plain_text": "Officer notes"}]}
            page = {"object": "page", "id": "p1", "url": "https://notion.so/p1", "properties": {"Name": title}}
            return Answer({"results": [page]})
        if url.endswith("/databases/d1"):
            return Answer({"properties": {"Event": {"type": "title"}}})
        if url.endswith("/pages"):
            return Answer({"object": "page", "id": "p2", "url": "https://notion.so/p2", "properties": {}})
        return Answer({"message": "nope"}, status=404)

    monkeypatch.setattr(notion.requests, "request", request)
    headers = _token(client, officer_headers, connected, ["notion:read", "notion:write"])
    found = client.post("/api/tools/notion.search", json={"query": "officer"}, headers=headers).get_json()
    assert found["result"]["results"][0]["title"] == "Officer notes"
    args = {"parent_id": "d1", "parent_type": "database", "title": "GBM", "content": "One\n\nTwo"}
    made = client.post("/api/tools/notion.create_page", json={**args, "confirm": True}, headers=headers)
    assert made.status_code == 200, made.get_json()
    body = calls[-1][2]
    assert body["properties"]["Event"] == {"title": [{"text": {"content": "GBM"}}]}
    assert len(body["children"]) == 2


def test_web_search_needs_searxng(client, officer_headers, orgs, monkeypatch):
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    headers = _token(client, officer_headers, orgs["soda"], ["web:read"])
    assert _names(client, headers, "web.") == []
    monkeypatch.setenv("SEARXNG_URL", "http://searxng.local")
    monkeypatch.setattr(web.web, "answer", lambda params: ("https://google.com", f"Web results for {params['query']}"))
    assert _names(client, headers, "web.") == ["web.search"]
    found = client.post("/api/tools/web.search", json={"query": "hackathons"}, headers=headers).get_json()
    assert found["result"]["text"] == "Web results for hackathons"
