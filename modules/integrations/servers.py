"""The MCP servers of connected services that Platform passes tools through to. No Flask here.

A server entry says where the service's MCP server is, how to sign in with the org's saved keys, the scopes
that give its read-only and its other tools, and how to find the repo or page a call acts on. The keys stay
on the server; an agent sees only the tools.
"""

import os
import re
from collections.abc import Callable
from dataclasses import dataclass

from core import secrets
from core.integrations import github
from modules.auth import machine_tokens, scopes


@dataclass(frozen=True)
class RemoteServer:
    # The integration key; tool names start with it, as github.list_issues
    key: str
    url: Callable[[], str]
    # The headers that sign in with the org's keys, or None when the org has none
    headers: Callable[[object, int], dict[str, str] | None]
    read_scope: str
    write_scope: str
    # The target a call acts on, as owner/name, or None when the arguments name no single target
    target: Callable[[dict], str | None]
    # The name of the token limit that lists the allowed targets
    target_limit: str


SERVERS: dict[str, RemoteServer] = {}


def register(server: RemoteServer) -> None:
    SERVERS[server.key] = server


# GitHub

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/(?:[A-Za-z0-9_.-]+|\*)$")
TOOL_PATTERN = re.compile(r"^[a-z0-9_.*?-]{1,100}$")
MAX_ITEMS = 50

scopes.declare("github:read", "Read the org's GitHub repos, issues, pull requests and Actions runs", "github")
scopes.declare(
    "github:write", "Create and change issues, pull requests, comments and files on GitHub (with confirm)", "github"
)


def _github_headers(db, org_id: int) -> dict[str, str] | None:
    token = secrets.get_secret(db, org_id, github.SECRET_NAME)
    return {"Authorization": f"Bearer {token}"} if token else None


def _github_target(arguments: dict) -> str | None:
    owner, repo = arguments.get("owner"), arguments.get("repo")
    if isinstance(owner, str) and isinstance(repo, str) and owner and repo:
        return f"{owner}/{repo}".lower()
    return None


def _check_list(value: object, name: str, pattern: re.Pattern, example: str) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > MAX_ITEMS:
        raise machine_tokens.TokenError(f"{name} must be a list of 1 to {MAX_ITEMS} items")
    cleaned = []
    for item in value:
        if not isinstance(item, str) or not pattern.match(item.strip().lower()):
            raise machine_tokens.TokenError(f"Not a valid {name} item: {item}. Example: {example}")
        if item.strip().lower() not in cleaned:
            cleaned.append(item.strip().lower())
    return cleaned


def _github_limits(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - {"repos", "tools"}:
        raise machine_tokens.TokenError("github limits take repos and tools")
    given: dict[str, object] = {str(k): v for k, v in value.items()}
    cleaned = {}
    if given.get("repos") is not None:
        cleaned["repos"] = _check_list(
            given["repos"], "repos", REPO_PATTERN, "theaisocietyasu/bedrock or theaisocietyasu/*"
        )
    if given.get("tools") is not None:
        cleaned["tools"] = _check_list(given["tools"], "tools", TOOL_PATTERN, "github.*issue*")
    return cleaned


machine_tokens.declare_limits("github", ("repos", "tools"), _github_limits)

register(
    RemoteServer(
        key="github",
        url=lambda: os.environ.get("GITHUB_MCP_URL", "https://api.githubcopilot.com/mcp/"),
        headers=_github_headers,
        read_scope="github:read",
        write_scope="github:write",
        target=_github_target,
        target_limit="repos",
    )
)
