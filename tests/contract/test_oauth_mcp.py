"""OAuth sign-in for MCP servers: Notion finds its URLs and registers a client, then its tools pass through."""

import json
import time
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet

from modules.integrations import mcp_client, oauth, service

BASE = "https://api.club.test"


class Answer:
    def __init__(self, body: dict, status: int = 200, sse: bool = False):
        self.status_code = status
        self.body = body
        self.headers = {"Content-Type": "text/event-stream" if sse else "application/json"}
        self.text = f"data: {json.dumps(body)}\n\n" if sse else json.dumps(body)

    def json(self):
        return self.body


@pytest.fixture
def notion(monkeypatch):
    """A fake Notion authorization server and MCP server. Records token requests and MCP headers."""
    seen: dict = {"tokens": [], "mcp": []}

    def get(url, timeout, headers=None):
        if url == "https://mcp.notion.com/.well-known/oauth-protected-resource/mcp":
            return Answer({"authorization_servers": ["https://mcp.notion.com"]})
        if url == "https://mcp.notion.com/.well-known/oauth-authorization-server":
            return Answer(
                {
                    "authorization_endpoint": "https://mcp.notion.com/authorize",
                    "token_endpoint": "https://mcp.notion.com/token",
                    "registration_endpoint": "https://mcp.notion.com/register",
                }
            )
        return Answer({}, status=404)

    def post(url, timeout, json=None, data=None, headers=None):
        if url == "https://mcp.notion.com/mcp":
            return mcp_post(url, json, headers, timeout)
        if url == "https://mcp.notion.com/register":
            assert json is not None and json["redirect_uris"] == [f"{BASE}{oauth.CALLBACK_PATH}"]
            return Answer({"client_id": "client-1"})
        if url == "https://mcp.notion.com/token":
            seen["tokens"].append(data)
            n = len(seen["tokens"])
            return Answer({"access_token": f"access-{n}", "refresh_token": "refresh-1", "expires_in": 3600})
        return Answer({}, status=404)

    def mcp_post(url, json, headers, timeout):
        seen["mcp"].append(headers["Authorization"])
        method = json["method"]
        if method == "notifications/initialized":
            return Answer({}, status=202)
        if method == "initialize":
            return Answer({"jsonrpc": "2.0", "id": json["id"], "result": {}})
        tools = [
            {"name": "notion-search", "description": "Search", "annotations": {"readOnlyHint": True}},
            {"name": "notion-create-pages", "description": "Create"},
        ]
        return Answer({"jsonrpc": "2.0", "id": json["id"], "result": {"tools": tools}}, sse=True)

    monkeypatch.setenv("ACCOUNTS_BASE_URL", BASE)
    monkeypatch.setattr(oauth.requests, "get", get)
    # oauth and mcp_client share the requests module, so one fake answers both
    assert oauth.requests is mcp_client.requests
    monkeypatch.setattr(oauth.requests, "post", post)
    service.clear_cache()
    yield seen
    service.clear_cache()


@pytest.fixture
def soda(client, officer_headers, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    org_id = next(o["id"] for o in orgs if o["prefix"] == "soda")
    yield org_id
    client.delete("/api/dashboard/soda/integrations/notion/oauth", headers=officer_headers)


def _connect(client, officer_headers):
    started = client.post("/api/dashboard/soda/integrations/notion/oauth", headers=officer_headers)
    assert started.status_code == 200, started.get_json()
    query = parse_qs(urlparse(started.get_json()["url"]).query)
    assert query["client_id"] == ["client-1"] and query["code_challenge_method"] == ["S256"]
    assert query["resource"] == ["https://mcp.notion.com/mcp"]
    return query["state"][0]


def test_sign_in_saves_tokens_and_tools_pass_through(client, officer_headers, soda, notion):
    state = _connect(client, officer_headers)
    back = client.get(f"/api/dashboard/integrations/oauth/callback?state={state}&code=abc")
    assert back.status_code in (200, 302)
    assert notion["tokens"][0]["code_verifier"] and notion["tokens"][0]["grant_type"] == "authorization_code"
    listed = client.get("/api/dashboard/soda/integrations", headers=officer_headers).get_json()
    assert listed["oauth"]["notion"]["connected"] is True
    body = {"name": "notes-agent", "kind": "agent", "scopes": ["notion:read"]}
    token = client.post(f"/api/organizations/{soda}/tokens", json=body, headers=officer_headers).get_json()["token"]
    tools = client.get("/api/tools", headers={"Authorization": f"Bearer {token}"}).get_json()["tools"]
    assert "notion.notion-search" in [t["name"] for t in tools]
    assert "notion.notion-create-pages" not in [t["name"] for t in tools]
    assert notion["mcp"][-1] == "Bearer access-1"


def test_a_state_works_once(client, officer_headers, soda, notion):
    state = _connect(client, officer_headers)
    assert client.get(f"/api/dashboard/integrations/oauth/callback?state={state}&code=abc").status_code in (200, 302)
    again = client.get(f"/api/dashboard/integrations/oauth/callback?state={state}&code=abc")
    assert again.status_code == 400
    forged = client.get(f"/api/dashboard/integrations/oauth/callback?state={soda}.notion.guess&code=abc")
    assert forged.status_code == 400


def test_an_expired_token_is_refreshed(client, officer_headers, soda, notion):
    from core.db import db_connect

    state = _connect(client, officer_headers)
    client.get(f"/api/dashboard/integrations/oauth/callback?state={state}&code=abc")
    db = db_connect.SessionLocal()
    try:
        raw = oauth.secrets.get_secret(db, soda, "oauth_notion")
        assert raw is not None
        saved = json.loads(raw)
        saved["expires_at"] = time.time() + 10
        oauth.secrets.set_secret(db, soda, "oauth_notion", json.dumps(saved))
        assert oauth.access_token(db, soda, "notion") == "access-2"
    finally:
        db.close()
    assert notion["tokens"][-1]["grant_type"] == "refresh_token"


def test_sign_in_needs_the_api_url(client, officer_headers, soda, monkeypatch):
    monkeypatch.delenv("ACCOUNTS_BASE_URL", raising=False)
    refused = client.post("/api/dashboard/soda/integrations/notion/oauth", headers=officer_headers)
    assert refused.status_code == 409
    listed = client.get("/api/dashboard/soda/integrations", headers=officer_headers).get_json()
    assert "ACCOUNTS_BASE_URL" in listed["oauth"]["notion"]["blocked"]
