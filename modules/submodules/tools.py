"""Submodule tools: the list and subscriptions for every org, and live queries when knowledge is on."""

from functools import partial

from core.tools import tool as _tool
from modules.knowledge import crawl
from modules.submodules import catalog, find, service

# Every tool here needs the knowledge module on for the caller's org
tool = partial(_tool, module="knowledge")

_LIST = "\n".join(
    f"- {submodule.name}/{q.key}: {q.description} Params: "
    + (", ".join(f"{p.name}{' (required)' if p.required else ''}" for p in q.params) or "none")
    for submodule in catalog.SUBMODULES.values()
    for q in submodule.queries
)


@tool(
    "knowledge.query",
    description="Ask a live source of shared content (a submodule) and get the text it returns with the URL to cite. "
    "Sources, as submodule/source:\n" + _LIST,
    scope="knowledge:read",
    input_schema={
        "type": "object",
        "properties": {
            "submodule": {"enum": sorted(name for name, submodule in catalog.SUBMODULES.items() if submodule.queries)},
            "source": {"type": "string", "maxLength": 100},
            "params": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 500}},
        },
        "required": ["submodule", "source"],
        "additionalProperties": False,
    },
)
def submodules_query(db, org, caller, submodule: str, source: str, params: dict | None = None):
    return service.query(db, int(org.id), str(org.prefix), submodule, source, params or {})


_SOURCE_HELP = " ".join(f"{key}: {q.description}" for key, (_, q) in find.SOURCES.items())


@tool(
    "search",
    description=(
        "Search for anything about the org's campus: stored pages first, then the live source you name, then the "
        "web. Nothing is looked up before you call it. Name a source for something current, such as hours today, "
        "open seats, shuttle times, events or scores. Send several searches with different wording in one step."
    ),
    scope="knowledge:read",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1000,
                "description": "What to search for, in keywords. It is the whole request: name the subject in full, "
                "with no pronoun. Bad: hours. Good: Hayden Library hours Sunday.",
            },
            "source": {
                "enum": list(find.SOURCES),
                "description": "Narrows the search to one source. Leave it out unless the question is plainly "
                "about that one source. " + _SOURCE_HELP,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def search(db, org, caller, query: str, source: str | None = None):
    return find.find(db, int(org.id), str(org.prefix), query, source)


NAME = {
    "type": "object",
    "properties": {"name": {"type": "string", "minLength": 1, "maxLength": 64}},
    "required": ["name"],
    "additionalProperties": False,
}


@_tool(
    "modules.submodules",
    description="All shared content (submodules, such as a campus or careers): its pages, live queries and feeds, the "
    "modules that read it, whether the org subscribes, and how many orgs do.",
    scope="submodules:read",
)
def submodules_list(db, org, caller):
    return {"submodules": service.list_submodules(db, int(org.id))}


@_tool(
    "modules.subscribe",
    description="Subscribe the org to shared content (a submodule): knowledge search reads its pages and its feeds become presets.",
    scope="submodules:manage",
    confirm=True,
    input_schema=NAME,
)
def submodules_subscribe(db, org, caller, name: str):
    result = service.subscribe(db, int(org.id), name, actor=caller.actor)
    crawl.start_crawl_due()
    return result


@_tool(
    "modules.unsubscribe",
    description="End the org's subscription to shared content (a submodule). Feeds the org already made keep running.",
    scope="submodules:manage",
    confirm=True,
    input_schema=NAME,
)
def submodules_unsubscribe(db, org, caller, name: str):
    return service.unsubscribe(db, int(org.id), name)
