"""search: the org's stored pages first, then the live query a source names, then the web. No Flask here."""

import datetime
import os
from zoneinfo import ZoneInfo

from modules.knowledge import embedder, search
from modules.knowledge.service import KnowledgeError
from modules.submodules import catalog, fill, service
from modules.submodules.types import QueryError, QuerySource, Submodule

#: The live query a search that names no source falls back to.
WEB = "web"

NOTHING = (
    "Nothing came back for that query. Search again with the subject named differently or with no source, or "
    "read the page when you know its url."
)
OLD = "Some pages are old. When the answer rests on a detail that changes, read the url again for the current page."


def _live_queries() -> dict[str, tuple[Submodule, QuerySource]]:
    """Every live query by key. The first submodule in name order keeps a key two of them share."""
    out: dict[str, tuple[Submodule, QuerySource]] = {}
    for submodule in catalog.SUBMODULES.values():
        for q in submodule.queries:
            out.setdefault(q.key, (submodule, q))
    return out


SOURCES = _live_queries()


def _stale_days() -> int:
    try:
        value = int(os.environ.get("SEARCH_STALE_DAYS", 14))
    except ValueError:
        return 14
    return value if value >= 1 else 14


def _old(fetched_at: str | None, now: datetime.datetime) -> bool:
    if not fetched_at:
        return False
    try:
        fetched = datetime.datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    return now - fetched > datetime.timedelta(days=_stale_days())


def _stored(db, org_id: int, query: str, category: str | None) -> dict | None:
    """Stored passages for query, or None when the org holds none."""
    found = search.search(db, org_id, query, category=category, embedder=embedder.for_org(db, org_id))["results"]
    if not found:
        return None
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    results = [
        {
            "title": r["title"],
            "url": r["url"],
            "fetched_at": r["fetched_at"],
            "content": r["content"],
        }
        for r in found
    ]
    out: dict = {"from": "stored", "results": results}
    if any(r["url"] and _old(r["fetched_at"], now) for r in results):
        out["note"] = OLD
    return out


def _live(db, org_id: int, org_prefix: str, key: str, query: str) -> dict:
    """One live query, its parameters filled from query. Raises KnowledgeError the caller can fix."""
    submodule, source = SOURCES[key]
    today = datetime.datetime.now(ZoneInfo(submodule.timezone)).date()
    try:
        params = fill.fill(source, query, today)
    except QueryError as e:
        raise KnowledgeError(str(e), 422) from e
    answer = service.query(db, org_id, org_prefix, submodule.name, key, params)
    return {"from": "live", "source": key, "url": answer["url"], "text": answer["text"]}


def find(db, org_id: int, org_prefix: str, query: object, source: object = None) -> dict:
    """The answer to query: stored pages, the named source live, or the web. Arguments come from callers."""
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise KnowledgeError("query must be text of at most 1000 characters")
    query = query.strip()
    if source in (None, ""):
        stored = _stored(db, org_id, query, None)
        if stored is not None:
            return stored
        if WEB not in SOURCES:
            return {"from": "none", "note": NOTHING}
        try:
            return _live(db, org_id, org_prefix, WEB, query)
        except KnowledgeError as e:
            return {"from": "none", "note": f"{NOTHING} The web search failed: {e.message}"}
    if not isinstance(source, str) or source not in SOURCES:
        raise KnowledgeError(f"source {source!r} is not one of: {', '.join(SOURCES)}")
    _, live = SOURCES[source]
    if live.index:
        stored = _stored(db, org_id, query, live.category)
        if stored is not None:
            return stored
    return _live(db, org_id, org_prefix, source, query)
