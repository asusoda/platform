"""ASU live query tool."""

from core.tools import ToolError, tool
from modules.asu import registry, service
from modules.knowledge.service import KnowledgeError

_LIST = "\n".join(
    f"- {q.key}: {q.description} Params: "
    + (", ".join(f"{p.name}{' (required)' if p.required else ''}" for p in q.params) or "none")
    for q in registry.QUERY_SOURCES.values()
)


@tool(
    "asu.query",
    description="Ask a live ASU source and get the text it returns with the URL to cite. Sources:\n" + _LIST,
    scope="knowledge:read",
    input_schema={
        "type": "object",
        "properties": {
            "source": {"enum": sorted(registry.QUERY_SOURCES)},
            "params": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 500}},
        },
        "required": ["source"],
        "additionalProperties": False,
    },
)
def asu_query(db, org, caller, source: str, params: dict | None = None):
    try:
        return service.query(db, int(org.id), str(org.prefix), source, params or {})
    except KnowledgeError as e:
        raise ToolError(e.message, e.status) from e
