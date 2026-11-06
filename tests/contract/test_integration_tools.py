"""Tools of connected services: GitHub's MCP server tools by scope, confirm, token limits and the org's key."""

import json

import pytest
from cryptography.fernet import Fernet

from modules.integrations import mcp_client, service

GITHUB_KEY = "github_pat_test_value"
TOOLS = [
    {
        "name": "list_issues",
        "description": "List issues in a repository.",
        "inputSchema": {
            "type": "object",
            "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
            "required": ["owner", "repo"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "search_code",
        "description": "Search code across GitHub.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "create_issue",
        "description": "Create an issue.",
        "inputSchema": {
            "type": "object",
            "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "title": {"type": "string"}},
            "required": ["owner", "repo", "title"],
        },
    },
]


class Reply:
    def __init__(self, message: dict, sse: bool = False, status: int = 200):
        self.status_code = status
        self.headers = {"Content-Type": "text/event-stream" if sse else "application/json", "Mcp-Session-Id": "s1"}
        self.message = message
        self.text = f"event: message\ndata: {json.dumps(message)}\n\n" if sse else json.dumps(message)

    def json(self):
        return self.message


@pytest.fixture
def github(monkeypatch):
    """A fake GitHub MCP server. Records each tools/call and the Authorization header it got."""
    calls: list = []

    def post(url, json, headers, timeout):
        assert headers["Authorization"] == f"Bearer {GITHUB_KEY}"
        method = json["method"]
        if method == "notifications/initialized":
            return Reply({}, status=202)
        if method == "initialize":
            return Reply({"jsonrpc": "2.0", "id": json["id"], "result": {"protocolVersion": "2025-06-18"}})
        if method == "tools/list":
            return Reply({"jsonrpc": "2.0", "id": json["id"], "result": {"tools": TOOLS}}, sse=True)
        calls.append(json["params"])
        result = {"content": [{"type": "text", "text": f"ran {json['params']['name']}"}]}
        return Reply({"jsonrpc": "2.0", "id": json["id"], "result": result}, sse=True)

    monkeypatch.setattr(mcp_client.requests, "post", post)
    service.clear_cache()
    yield calls
    service.clear_cache()


@pytest.fixture
def soda(client, officer_headers, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    org_id = next(o["id"] for o in orgs if o["prefix"] == "soda")
    saved = client.put(
        "/api/dashboard/soda/integrations/github",
        json={"fields": {"github_token": GITHUB_KEY}},
        headers=officer_headers,
    )
    assert saved.status_code == 200, saved.get_json()
    yield org_id
    client.put(
        "/api/dashboard/soda/integrations/github", json={"fields": {"github_token": None}}, headers=officer_headers
    )


def _token(client, officer_headers, org_id, scopes, limits=None):
    body = {"name": "ops-agent", "kind": "agent", "scopes": scopes, "limits": limits}
    response = client.post(f"/api/organizations/{org_id}/tokens", json=body, headers=officer_headers)
    assert response.status_code == 201, response.get_json()
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def _names(client, headers):
    return [t["name"] for t in client.get("/api/tools", headers=headers).get_json()["tools"]]


def test_scopes_pick_read_and_write_tools(client, officer_headers, soda, github):
    reader = _token(client, officer_headers, soda, ["github:read"])
    assert _names(client, reader) == ["batch", "github.list_issues", "github.search_code"]
    writer = _token(client, officer_headers, soda, ["github:read", "github:write"])
    assert _names(client, writer) == ["batch", "github.create_issue", "github.list_issues", "github.search_code"]
    listed = client.get("/api/tools", headers=writer).get_json()["tools"]
    create = next(t for t in listed if t["name"] == "github.create_issue")
    assert (
        create["confirm"] is True and create["read_only"] is False and "confirm" in create["input_schema"]["properties"]
    )


def test_calls_pass_through_and_writes_need_confirm(client, officer_headers, soda, github):
    headers = _token(client, officer_headers, soda, ["github:read", "github:write"])
    read = client.post("/api/tools/github.list_issues", json={"owner": "ais", "repo": "bedrock"}, headers=headers)
    assert read.status_code == 200, read.get_json()
    assert read.get_json()["result"]["text"] == "ran list_issues"
    args = {"owner": "ais", "repo": "bedrock", "title": "Bug"}
    pending = client.post("/api/tools/github.create_issue", json=args, headers=headers).get_json()["result"]
    assert pending["confirm_required"] is True
    assert [c["name"] for c in github] == ["list_issues"]
    done = client.post("/api/tools/github.create_issue", json={**args, "confirm": True}, headers=headers)
    assert done.status_code == 200 and github[-1] == {"name": "create_issue", "arguments": args}


def test_repo_and_tool_limits(client, officer_headers, soda, github):
    limits = {"github": {"repos": ["AIS/*"]}}
    headers = _token(client, officer_headers, soda, ["github:read", "github:write"], limits)
    assert _names(client, headers) == ["batch", "github.create_issue", "github.list_issues"]
    other = client.post("/api/tools/github.list_issues", json={"owner": "soda", "repo": "x"}, headers=headers)
    assert other.status_code == 403
    assert (
        client.post("/api/tools/github.list_issues", json={"owner": "ais", "repo": "x"}, headers=headers).status_code
        == 200
    )
    narrow = _token(client, officer_headers, soda, ["github:read"], {"github": {"tools": ["github.list_*"]}})
    assert _names(client, narrow) == ["batch", "github.list_issues"]
    assert client.post("/api/tools/github.search_code", json={"query": "x"}, headers=narrow).status_code == 404
    bad = {"name": "x", "kind": "agent", "scopes": ["github:read"], "limits": {"github": {"repos": ["no slash"]}}}
    assert client.post(f"/api/organizations/{soda}/tokens", json=bad, headers=officer_headers).status_code == 400
    unknown = {**bad, "limits": {"slack": {}}}
    assert client.post(f"/api/organizations/{soda}/tokens", json=unknown, headers=officer_headers).status_code == 400


def test_no_tools_without_the_org_key(client, officer_headers, github):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    ais = next(o["id"] for o in orgs if o["prefix"] == "ais")
    headers = _token(client, officer_headers, ais, ["github:read"])
    assert _names(client, headers) == []
    assert client.post("/api/tools/github.list_issues", json={}, headers=headers).status_code == 404


def test_token_list_groups_integration_scopes(client, officer_headers, soda):
    body = client.get(f"/api/organizations/{soda}/tokens", headers=officer_headers).get_json()
    github = next(i for i in body["integrations"] if i["key"] == "github")
    assert {k: v for k, v in github.items() if k != "used_by"} == {
        "key": "github",
        "title": "GitHub",
        "connected": True,
        "scopes": ["github:read", "github:write"],
        "through": ["apps:manage"],
        "limits": ["repos", "tools"],
        "tools": {},
        "remote": True,
    }
    assert "integrations" in github["used_by"]
    google = next(i for i in body["integrations"] if i["key"] == "google")
    assert google["scopes"] == ["gmail:read", "gmail:send", "google:read", "google:write"]
    assert "google.calendar_events" in google["tools"]["google:read"] and google["remote"] is True
    notion = next(i for i in body["integrations"] if i["key"] == "notion")
    assert notion["tools"]["notion:write"] == ["notion.create_page"]
    keys = [i["key"] for i in body["integrations"]]
    assert {"discord", "embeddings", "notion", "runpod"} <= set(keys)
    runpod = next(i for i in body["integrations"] if i["key"] == "runpod")
    assert runpod["scopes"] == ["runpod:read", "runpod:write"] and runpod["remote"] is True
    assert "godfather:manage" in runpod["through"]
    assert body["uses"]["knowledge:write"] == ["embeddings", "firecrawl"]
    assert "org:read" not in body["uses"]


def test_remote_errors_are_tool_errors(client, officer_headers, soda, monkeypatch):
    def refused(url, json, headers, timeout):
        return Reply({}, status=401)

    monkeypatch.setattr(mcp_client.requests, "post", refused)
    service.clear_cache()
    headers = _token(client, officer_headers, soda, ["github:read"])
    assert _names(client, headers) == []


@pytest.mark.parametrize(
    "owner, repo",
    [("ais", "../soda/x"), ("ais", ".."), ("ais/../soda", "x"), ("ais", "x/../../soda/y"), ("ais", "x?y")],
)
def test_repo_limit_refuses_path_parts(client, officer_headers, soda, github, owner, repo):
    headers = _token(client, officer_headers, soda, ["github:read"], {"github": {"repos": ["ais/*"]}})
    response = client.post("/api/tools/github.list_issues", json={"owner": owner, "repo": repo}, headers=headers)
    assert response.status_code == 403
    assert github == []


WRITES = [
    {
        "name": name,
        "description": name,
        "inputSchema": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}}},
    }
    for name in ("push_files", "merge_pull_request")
]


class Rest:
    def __init__(self, body: dict):
        self.status_code = 200
        self.body = body

    def json(self):
        return self.body


@pytest.fixture
def rest(monkeypatch):
    """A fake GitHub REST API: default branch main, and pull request 7 with the checks in state."""
    from core.integrations import github as github_rest

    state = {"conclusion": "success"}

    def get(url, params=None, headers=None, timeout=None):
        path = url.removeprefix(github_rest.API)
        if path.endswith("/pulls/7"):
            return Rest({"state": "open", "head": {"sha": "abc"}})
        if path.endswith("/check-runs"):
            return Rest({"check_runs": [{"name": "check", "status": "completed", "conclusion": state["conclusion"]}]})
        if path.endswith("/status"):
            return Rest({"state": "pending", "statuses": []})
        return Rest({"default_branch": "main"})

    monkeypatch.setattr(github_rest.requests, "get", get)
    return state


@pytest.fixture
def writer(client, officer_headers, soda, github, rest, monkeypatch):
    monkeypatch.setattr(f"{__name__}.TOOLS", TOOLS + WRITES)
    service.clear_cache()
    yield _token(client, officer_headers, soda, ["github:read", "github:write"])
    client.put("/api/dashboard/soda/ci/repos", json={"repos": []}, headers=officer_headers)


def _write(client, headers, name, **arguments):
    return client.post(
        f"/api/tools/github.{name}",
        json={"owner": "ais", "repo": "site", "confirm": True, **arguments},
        headers=headers,
    )


def test_file_writes_never_go_to_the_default_branch(client, writer, github):
    assert _write(client, writer, "push_files", branch="main").status_code == 403
    assert _write(client, writer, "push_files").status_code == 400
    assert _write(client, writer, "push_files", branch="fix-footer").status_code == 200
    assert [c["name"] for c in github] == ["push_files"]


def test_merge_waits_for_green_checks(client, writer, github, rest):
    rest["conclusion"] = "failure"
    refused = _write(client, writer, "merge_pull_request", pullNumber=7)
    assert refused.status_code == 409 and "check" in refused.get_json()["error"]
    rest["conclusion"] = "success"
    assert _write(client, writer, "merge_pull_request", pullNumber=7).status_code == 200


def test_writes_stay_on_linked_repos(client, officer_headers, writer):
    client.put("/api/dashboard/soda/ci/repos", json={"repos": ["AIS/site"]}, headers=officer_headers)
    assert _write(client, writer, "create_issue", title="Bug").status_code == 200
    other = client.post(
        "/api/tools/github.create_issue",
        json={"owner": "ais", "repo": "other", "title": "Bug", "confirm": True},
        headers=writer,
    )
    assert other.status_code == 403
    read = client.post("/api/tools/github.list_issues", json={"owner": "ais", "repo": "other"}, headers=writer)
    assert read.status_code == 200


def test_results_hide_org_secrets_and_ask_for_actions(client, officer_headers, soda, monkeypatch):
    seen = {}

    def post(url, json, headers, timeout):
        seen["toolsets"] = headers.get("X-MCP-Toolsets")
        if json["method"] == "notifications/initialized":
            return Reply({}, status=202)
        if json["method"] == "tools/list":
            return Reply({"jsonrpc": "2.0", "id": json["id"], "result": {"tools": TOOLS}})
        result = {"content": [{"type": "text", "text": f"log line token={GITHUB_KEY}"}]}
        return Reply({"jsonrpc": "2.0", "id": json["id"], "result": result})

    monkeypatch.setattr(mcp_client.requests, "post", post)
    service.clear_cache()
    headers = _token(client, officer_headers, soda, ["github:read"])
    read = client.post("/api/tools/github.list_issues", json={"owner": "ais", "repo": "x"}, headers=headers)
    assert read.get_json()["result"]["text"] == "log line token=[secret]"
    assert "actions" in seen["toolsets"]
    service.clear_cache()
