"""The web search tool for agents, through the org's SearXNG or the deployment's. No Flask here."""

from functools import partial

from core.integrations import registry
from core.tools import ToolError
from core.tools import tool as _tool
from modules.auth import scopes
from modules.knowledge import fetch
from modules.knowledge.submodules.web import query as web
from modules.knowledge.content.search import query_scope
from modules.knowledge.content.types import QueryError

# Every tool here needs the knowledge.web sub-module on for the caller's org
tool = partial(_tool, module="knowledge.web")

registry.use("searxng", "knowledge")
scopes.declare("web:read", "Search the web through the org's SearXNG", "searxng")


def connected(db, org_id: int) -> bool:
    """The org or the deployment has a SearXNG server."""
    return registry.connected(db, org_id, "searxng")


@tool(
    "knowledge.web_search",
    description="Search the web through Google, Brave and Bing. Returns titles, links, dates and snippets.",
    scope="web:read",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 500},
            "time_range": {"enum": ["day", "week", "month", "year"]},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    integration="searxng",
    available=connected,
)
def web_search(db, org, caller, query: str, time_range: str | None = None):
    params = {"query": query, **({"time_range": time_range} if time_range else {})}
    try:
        with query_scope(db, int(org.id)):
            citation, text = web.answer(params)
    except QueryError as e:
        raise ToolError(str(e), 404) from e
    except fetch.FetchRejected as e:
        raise ToolError(str(e), 422) from e
    except fetch.FetchError as e:
        raise ToolError(str(e), 502) from e
    return {"text": text, "citation": citation}
