"""Notion tools for agents with the org's integration token. No Flask here.

The tools use only the org's own token, never the deployment default, so an agent reads only its own org's
workspace. Notion shows the integration only the pages and databases shared with it.
"""

from typing import Any
from urllib.parse import quote

import requests

from core.integrations import registry
from core.tools import ToolError, tool
from modules.auth import scopes
from modules.calendar.integrations import NOTION_SECRET

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
TIMEOUT_SECONDS = 30
MAX_BLOCKS = 500
MAX_DEPTH = 2
MAX_TEXT_CHARS = 100_000
MAX_PARAGRAPH_CHARS = 2000
MAX_NEW_BLOCKS = 100

registry.use("notion", "integrations")
scopes.declare(
    "notion:read", "Search and read the Notion pages and databases shared with the org's integration", "notion"
)
scopes.declare("notion:write", "Create Notion pages and database rows (with confirm)", "notion")


def connected(db, org_id: int) -> bool:
    """The org saved its own Notion token."""
    return registry.org_values(db, org_id, "notion") is not None


def _reason(response: requests.Response) -> str:
    try:
        return str(response.json().get("message") or "")[:300]
    except (ValueError, AttributeError):
        return response.text.strip()[:300]


def call(db, org, method: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    """One Notion API request. Raises ToolError with Notion's reason when it fails."""
    saved = registry.org_values(db, int(org.id), "notion")
    if saved is None:
        raise ToolError("Connect Notion on the Integrations page first", 409)
    headers = {"Authorization": f"Bearer {saved[NOTION_SECRET]}", "Notion-Version": VERSION}
    try:
        response = requests.request(
            method, f"{API}{path}", headers=headers, json=body, params=params, timeout=TIMEOUT_SECONDS
        )
    except requests.RequestException as e:
        raise ToolError("Notion could not be reached", 502) from e
    if response.status_code == 404:
        raise ToolError("Notion found nothing there, or it is not shared with the integration", 404)
    if response.status_code in (401, 403):
        raise ToolError(f"Notion refused: {_reason(response)}", 403)
    if response.status_code >= 400:
        raise ToolError(f"Notion answered {response.status_code}: {_reason(response)}", 422)
    return response.json()


def _rich(items: Any) -> str:
    return "".join(str(i.get("plain_text") or "") for i in items or [] if isinstance(i, dict))


def value(prop: dict) -> Any:
    """A Notion property as a plain value."""
    kind = prop.get("type")
    data = prop.get(kind) if isinstance(kind, str) else None
    if kind in ("title", "rich_text"):
        return _rich(data)
    if kind in ("select", "status"):
        return data.get("name") if isinstance(data, dict) else None
    if kind == "multi_select":
        return [o.get("name") for o in data or []]
    if kind == "date":
        return {"start": data.get("start"), "end": data.get("end")} if isinstance(data, dict) else None
    if kind == "people":
        return [p.get("name") or p.get("id") for p in data or []]
    if kind == "relation":
        return [r.get("id") for r in data or []]
    if kind == "formula" and isinstance(data, dict):
        return data.get(data.get("type"))
    return data


def _title(item: dict) -> str:
    if item.get("object") == "database":
        return _rich(item.get("title"))
    for prop in (item.get("properties") or {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _rich(prop.get("title"))
    return ""


def _summary(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "type": item.get("object"),
        "title": _title(item),
        "url": item.get("url"),
        "last_edited": item.get("last_edited_time"),
    }


PREFIX = {
    "heading_1": "# ",
    "heading_2": "## ",
    "heading_3": "### ",
    "bulleted_list_item": "- ",
    "numbered_list_item": "1. ",
    "quote": "> ",
    "callout": "> ",
}


def _line(block: dict) -> str | None:
    kind = str(block.get("type"))
    found = block.get(kind)
    data: dict = found if isinstance(found, dict) else {}
    if kind == "to_do":
        return f"[{'x' if data.get('checked') else ' '}] {_rich(data.get('rich_text'))}"
    if kind == "code":
        return f"```\n{_rich(data.get('rich_text'))}\n```"
    if kind == "child_page":
        return f"[page] {data.get('title')} ({block.get('id')})"
    if kind == "child_database":
        return f"[database] {data.get('title')} ({block.get('id')})"
    if kind == "divider":
        return "---"
    if "rich_text" in data:
        return PREFIX.get(kind, "") + _rich(data.get("rich_text"))
    return None


def _blocks(db, org, block_id: str, depth: int, lines: list[str]) -> None:
    cursor = None
    while len(lines) < MAX_BLOCKS:
        params = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
        found = call(db, org, "GET", f"/blocks/{quote(block_id, safe='')}/children", params=params)
        for block in found.get("results") or []:
            line = _line(block)
            if line is not None:
                lines.append("  " * depth + line)
            if block.get("has_children") and depth + 1 < MAX_DEPTH and block.get("type") not in ("child_page",):
                _blocks(db, org, str(block.get("id")), depth + 1, lines)
            if len(lines) >= MAX_BLOCKS:
                return
        cursor = found.get("next_cursor")
        if not found.get("has_more") or not cursor:
            return


ID = {"type": "string", "minLength": 1, "maxLength": 100}


@tool(
    "notion.search",
    description="Search the Notion pages and databases shared with the org's integration, by title.",
    scope="notion:read",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "maxLength": 200},
            "type": {"enum": ["page", "database"]},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "additionalProperties": False,
    },
    integration="notion",
    available=connected,
)
def notion_search(db, org, caller, query: str = "", type: str | None = None, max_results: int = 20):
    body: dict[str, Any] = {"query": query, "page_size": max_results}
    if type:
        body["filter"] = {"property": "object", "value": type}
    found = call(db, org, "POST", "/search", body)
    return {"results": [_summary(item) for item in found.get("results") or []]}


@tool(
    "notion.read_page",
    description="A Notion page: its properties and its content as text. Child pages are listed, not read.",
    scope="notion:read",
    input_schema={
        "type": "object",
        "properties": {"page_id": ID},
        "required": ["page_id"],
        "additionalProperties": False,
    },
    integration="notion",
    available=connected,
)
def notion_read_page(db, org, caller, page_id: str):
    page = call(db, org, "GET", f"/pages/{quote(page_id, safe='')}")
    lines: list[str] = []
    _blocks(db, org, page_id, 0, lines)
    text = "\n".join(lines)
    return {
        **_summary(page),
        "properties": {name: value(prop) for name, prop in (page.get("properties") or {}).items()},
        "text": text[:MAX_TEXT_CHARS],
        "truncated": len(text) > MAX_TEXT_CHARS or len(lines) >= MAX_BLOCKS,
    }


@tool(
    "notion.query_database",
    description="Rows of a Notion database with their properties. filter and sorts take the Notion API's "
    "database query format.",
    scope="notion:read",
    input_schema={
        "type": "object",
        "properties": {
            "database_id": ID,
            "filter": {"type": "object"},
            "sorts": {"type": "array", "maxItems": 10, "items": {"type": "object"}},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "required": ["database_id"],
        "additionalProperties": False,
    },
    integration="notion",
    available=connected,
)
def notion_query_database(
    db, org, caller, database_id: str, filter: dict | None = None, sorts: list | None = None, max_results: int = 50
):
    body: dict[str, Any] = {"page_size": max_results}
    if filter:
        body["filter"] = filter
    if sorts:
        body["sorts"] = sorts
    found = call(db, org, "POST", f"/databases/{quote(database_id, safe='')}/query", body)
    return {
        "rows": [
            {
                "id": row.get("id"),
                "url": row.get("url"),
                "properties": {name: value(prop) for name, prop in (row.get("properties") or {}).items()},
            }
            for row in found.get("results") or []
        ],
        "more": bool(found.get("has_more")),
    }


def _paragraphs(content: str) -> list[dict]:
    blocks = []
    for part in [p.strip() for p in content.split("\n\n") if p.strip()]:
        for start in range(0, len(part), MAX_PARAGRAPH_CHARS):
            text = part[start : start + MAX_PARAGRAPH_CHARS]
            blocks.append(
                {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": text}}]}}
            )
    return blocks[:MAX_NEW_BLOCKS]


@tool(
    "notion.create_page",
    description="Create a Notion page under a page, or a row in a database. content is plain text; a blank "
    "line starts a new paragraph. properties sets other database columns in the Notion API's format.",
    scope="notion:write",
    input_schema={
        "type": "object",
        "properties": {
            "parent_id": ID,
            "parent_type": {"enum": ["page", "database"]},
            "title": {"type": "string", "minLength": 1, "maxLength": 2000},
            "content": {"type": "string", "maxLength": 100_000},
            "properties": {"type": "object"},
        },
        "required": ["parent_id", "parent_type", "title"],
        "additionalProperties": False,
    },
    confirm=True,
    integration="notion",
    available=connected,
)
def notion_create_page(
    db,
    org,
    caller,
    parent_id: str,
    parent_type: str,
    title: str,
    content: str = "",
    properties: dict | None = None,
):
    title_value = [{"text": {"content": title}}]
    if parent_type == "database":
        schema = call(db, org, "GET", f"/databases/{quote(parent_id, safe='')}")
        title_name = next(
            (
                n
                for n, p in (schema.get("properties") or {}).items()
                if isinstance(p, dict) and p.get("type") == "title"
            ),
            "Name",
        )
        body: dict[str, Any] = {
            "parent": {"database_id": parent_id},
            "properties": {**(properties or {}), title_name: {"title": title_value}},
        }
    else:
        body = {"parent": {"page_id": parent_id}, "properties": {"title": {"title": title_value}}}
    if content:
        body["children"] = _paragraphs(content)
    return _summary(call(db, org, "POST", "/pages", body))
