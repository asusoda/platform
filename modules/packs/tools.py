"""Live pack query tool."""

from core.tools import tool
from modules.packs import catalog, service

_LIST = "\n".join(
    f"- {pack.name}/{q.key}: {q.description} Params: "
    + (", ".join(f"{p.name}{' (required)' if p.required else ''}" for p in q.params) or "none")
    for pack in catalog.PACKS.values()
    for q in pack.queries
)


@tool(
    "packs.query",
    description="Ask a live source of a pack and get the text it returns with the URL to cite. "
    "Sources, as pack/source:\n" + _LIST,
    scope="knowledge:read",
    input_schema={
        "type": "object",
        "properties": {
            "pack": {"enum": sorted(name for name, pack in catalog.PACKS.items() if pack.queries)},
            "source": {"type": "string", "maxLength": 100},
            "params": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 500}},
        },
        "required": ["pack", "source"],
        "additionalProperties": False,
    },
)
def packs_query(db, org, caller, pack: str, source: str, params: dict | None = None):
    return service.query(db, int(org.id), str(org.prefix), pack, source, params or {})
