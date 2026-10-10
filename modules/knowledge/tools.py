"""Knowledge tools."""

from core.tools import tool
from modules.knowledge import embedder, search


@tool(
    "knowledge.search",
    description=(
        "Search the organization's knowledge and public sources. Returns ranked passages with their "
        "source title, URL and fetch time."
    ),
    scope="knowledge:read",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 1000},
            "category": {"type": "string", "maxLength": 100},
            "top_k": {"type": "integer", "minimum": 1, "maximum": search.MAX_TOP_K},
            "window": {"type": "integer", "minimum": 0, "maximum": search.MAX_WINDOW},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def knowledge_search(
    db, org, caller, query: str, category: str | None = None, top_k: int | None = None, window: int | None = None
):
    return search.search(
        db,
        int(org.id),
        query,
        category=category,
        top_k=top_k,
        window=window,
        embedder=embedder.for_org(db, int(org.id)),
    )
