"""Knowledge tools."""

from core.tools import ToolError, tool
from modules.knowledge import embedder, service


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
            "top_k": {"type": "integer", "minimum": 1, "maximum": service.MAX_TOP_K, "default": 8},
            "window": {"type": "integer", "minimum": 0, "maximum": service.MAX_WINDOW, "default": 0},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def knowledge_search(db, org, caller, query: str, category: str | None = None, top_k: int = 8, window: int = 0):
    try:
        return service.search(
            db, int(org.id), query, category=category, top_k=top_k, window=window, embedder=embedder.configured()
        )
    except service.KnowledgeError as e:
        raise ToolError(e.message, e.status) from e
