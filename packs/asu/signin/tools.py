"""ASU tools for agents that read Sun Devil Central with the org's ASU sign-in. No Flask here.

The tools show only when the API has the browser and the org saved an ASU sign-in. They are read-only.
Their results go back to the caller only and are never added to knowledge.
"""

from core.tools import ToolError, tool
from modules.auth import scopes
from modules.knowledge import fetch
from modules.packs.search import query_scope, settings
from modules.packs.types import QueryError
from packs.asu.queries import events as public_events
from packs.asu.signin import service, sundevil_central

scopes.declare("asu:read", "Search ASU clubs and events on Sun Devil Central with the org's ASU sign-in")


def _fit(body: str, budget: int) -> str:
    """body cut at a line end to fit budget characters."""
    if len(body) <= budget:
        return body
    return body[:budget].rsplit("\n", 1)[0] + "\n[more listings not shown]"


@tool(
    "asu.clubs",
    description="Search ASU student clubs on Sun Devil Central by name or topic. Returns each club with its "
    "campus, categories, link, contact and mission.",
    scope="asu:read",
    input_schema={
        "type": "object",
        "properties": {"keywords": {"type": "string", "minLength": 1, "maxLength": 200}},
        "required": ["keywords"],
        "additionalProperties": False,
    },
    available=service.usable,
)
def asu_clubs(db, org, caller, keywords: str):
    url = sundevil_central.clubs_url(keywords)
    fetched = service.read(db, int(org.id), str(org.prefix), url)
    text = sundevil_central.extract_clubs(fetched)
    return {"text": _fit(text, settings().scraper.query_max_chars), "citation": url}


@tool(
    "asu.events",
    description="Search ASU events: the Sun Devil Central listings and the public ASU events calendar. "
    "Returns one line per event with its time, place and link.",
    scope="asu:read",
    input_schema={
        "type": "object",
        "properties": {"keywords": {"type": "string", "maxLength": 200}},
        "additionalProperties": False,
    },
    available=service.usable,
)
def asu_events(db, org, caller, keywords: str = ""):
    org_id, budget = int(org.id), settings().scraper.query_max_chars // 2
    sections: list[str] = []
    citation: str | None = None
    url = sundevil_central.events_url(keywords)
    try:
        body = sundevil_central.extract_events(service.read(db, org_id, str(org.prefix), url))
        sections.append(f"Sun Devil Central\n{_fit(body.strip(), budget)}")
        citation = url
    except service.AsuError as e:
        sections.append(f"Sun Devil Central was not read: {e.message}.")
    try:
        with query_scope(db, org_id):
            public_url, body = public_events.public(keywords)
        if body.strip():
            sections.append(f"ASU Events\n{_fit(body.strip(), budget)}")
            citation = citation or public_url
    except (QueryError, fetch.FetchError, fetch.FetchRejected) as e:
        sections.append(f"The ASU events calendar was not read: {e}.")
    if citation is None:
        raise ToolError("No events found. " + " ".join(sections), 502)
    return {"text": "\n\n".join(sections), "citation": citation}
