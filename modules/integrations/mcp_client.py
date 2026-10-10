"""A small MCP client over streamable HTTP for the servers of connected services. No Flask here.

It sends JSON-RPC requests with requests and reads an answer sent as JSON or as server-sent events.
Each call starts a session (initialize), so the client keeps no state between calls.
"""

import json
from typing import Any

import requests

PROTOCOL_VERSION = "2025-06-18"
TIMEOUT_SECONDS = 30
MAX_PAGES = 10


class RemoteError(RuntimeError):
    """The remote server could not be reached or refused the request. The message has no secret in it."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class Session:
    def __init__(self, url: str, headers: dict[str, str]):
        self.url = url
        self.headers = {
            **headers,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        self.next_id = 0

    def _post(self, body: dict) -> requests.Response:
        try:
            response = requests.post(self.url, json=body, headers=self.headers, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as e:
            raise RemoteError("The server could not be reached") from e
        if response.status_code in (401, 403):
            raise RemoteError("The server refused the org's key. Check it on the Integrations page", 502)
        if response.status_code >= 400:
            raise RemoteError(f"The server answered {response.status_code}")
        return response

    def request(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        body = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}}
        response = self._post(body)
        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self.headers["Mcp-Session-Id"] = session_id
        message = _answer(response, self.next_id)
        if "error" in message:
            error = message["error"] if isinstance(message["error"], dict) else {}
            raise RemoteError(str(error.get("message") or "The server returned an error"), 502)
        result = message.get("result")
        if not isinstance(result, dict):
            raise RemoteError("The server sent an answer with no result")
        return result

    def notify(self, method: str) -> None:
        self._post({"jsonrpc": "2.0", "method": method})

    def open(self) -> "Session":
        self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "platform", "version": "1"},
            },
        )
        self.notify("notifications/initialized")
        return self


def _answer(response: requests.Response, request_id: int) -> dict:
    """The JSON-RPC message that answers request_id, from a JSON body or an event stream."""
    kind = response.headers.get("Content-Type", "")
    if "text/event-stream" in kind:
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            try:
                message = json.loads(line[5:].strip())
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("id") == request_id:
                return message
        raise RemoteError("The server sent no answer")
    try:
        message = response.json()
    except ValueError as e:
        raise RemoteError("The server did not send JSON") from e
    if not isinstance(message, dict):
        raise RemoteError("The server sent an answer that is not an object")
    return message


def list_tools(url: str, headers: dict[str, str]) -> list[dict]:
    """Every tool the server lists, following pages."""
    session = Session(url, headers).open()
    tools: list[dict] = []
    cursor = None
    for _ in range(MAX_PAGES):
        result = session.request("tools/list", {"cursor": cursor} if cursor else {})
        tools += [t for t in result.get("tools") or [] if isinstance(t, dict) and isinstance(t.get("name"), str)]
        cursor = result.get("nextCursor")
        if not cursor:
            break
    return tools


def call_tool(url: str, headers: dict[str, str], name: str, arguments: dict[str, Any]) -> dict:
    """The result of one tool call: content, structuredContent and isError as the server sent them."""
    return Session(url, headers).open().request("tools/call", {"name": name, "arguments": arguments})
