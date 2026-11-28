"""Shared sub-modules and the live queries of knowledge content. No Flask here.

A shared sub-module, such as knowledge.asu or feeds.jobs, holds content made once for every org. An org turns it on
with its switch (modules/organizations/service.py set_modules), which also writes the subscription row in
core/submodules.py. The pages of a knowledge sub-module are its own sources (knowledge_sources.submodule_id, no
org), under keys that start with <content>/. The deployment crawls and embeds them once, with its own embedder,
Firecrawl and chunk settings, while one or more orgs subscribe. A subscribed org's search reads them. A live query
fetches one page or API with parameters, answers the caller, and then indexes what it read as a source of the org.
"""

import hashlib
from functools import partial
from typing import Any, cast

from sqlalchemy import func

from core import submodules
from core.jobs import defer
from core.log import get_logger
from core.submodules import SharedContent, SubmoduleSubscription, Submodule, row_for, subscribed_keys
from core.time import utcnow
from modules.auth import scopes
from modules.knowledge import crawl, fetch
from modules.knowledge.content import catalog, queries, signins
from modules.knowledge.content.search import query_scope, settings
from modules.knowledge.content.types import Content, QueryError
from modules.knowledge.embedder import Embedder
from modules.knowledge.models import KnowledgeSource, KnowledgeVersion
from modules.knowledge.service import KnowledgeError, can_publish, new_source
from modules.organizations import service as organizations
from modules.organizations.models import Organization

logger = get_logger("knowledge.shared")

scopes.declare("submodules:read", "List the shared sub-modules and which ones the org has on")
scopes.declare("submodules:manage", "Turn the org's shared sub-modules on or off")

# Names from before the sub-modules, which clients still send: careers held both feeds sub-modules
OLD_NAMES = {"careers": ("feeds.jobs", "feeds.hackathons")}


def resolve(name: object) -> list[Submodule]:
    """The shared sub-modules a name stands for: a key such as knowledge.asu, a short name such as asu, or careers."""
    found = [s for s in submodules.shared() if name in (s.key, s.name)]
    if not found and isinstance(name, str):
        found = [s for key in OLD_NAMES.get(name, ()) if (s := submodules.get(key)) is not None]
    if not found:
        raise KnowledgeError(f"No shared content named {name}", 404)
    return found


def _content(name: object) -> Content:
    """The knowledge content by its name (asu) or the key of its sub-module (knowledge.asu)."""
    content = catalog.get(name)
    if content is None and isinstance(name, str) and (sub := submodules.get(name)) is not None:
        content = catalog.of(sub)
    if content is None:
        raise KnowledgeError(f"No shared content named {name}", 404)
    return content


def _parts(sub: Submodule, content: Content | None) -> list[dict]:
    """What the sub-module brings to a subscribed org, and who pays for each part (see core.limits.PAID_BY)."""
    parts = []
    if content is not None and content.sources:
        parts.append({"kind": "pages", "count": len(content.sources), "paid_by": "shared", "module": sub.module})
    if content is not None and content.queries:
        # A live result is indexed as a source of the org, so it counts against the org's knowledge limits
        parts.append({"kind": "queries", "count": len(content.queries), "paid_by": "org", "module": sub.module})
    feeds = submodules.attribute(sub.key, "FEEDS", ())
    if feeds:
        # A feed made from a preset is the org's own feed and webhook
        parts.append({"kind": "feeds", "count": len(feeds), "paid_by": "org", "module": sub.module})
    return parts


def list_submodules(db, org_id: int) -> list[dict]:
    """Every shared sub-module, whether the org subscribes, how many orgs do, its shared pages and its last crawl."""
    rows = {r.key: r for r in db.query(SharedContent).all()}
    mine = subscribed_keys(db, org_id)
    result = []
    for sub in submodules.shared():
        content = catalog.of(sub)
        row = rows.get(sub.key)
        stats = (0, None)
        subscribers = 0
        if row is not None:
            stats = (
                db.query(func.count(KnowledgeSource.id), func.max(KnowledgeSource.last_attempt_at))
                .filter(KnowledgeSource.submodule_id == row.id, KnowledgeSource.enabled.is_(True))
                .one()
            )
            subscribers = db.query(SubmoduleSubscription).filter_by(submodule_id=row.id).count()
        result.append(
            {
                "name": sub.name,
                "key": sub.key,
                "title": sub.title,
                "description": sub.description,
                "key_prefix": content.key_prefix if content else None,
                "pages": len(content.sources) if content else 0,
                "queries": [q.key for q in content.queries] if content else [],
                "feeds": [f.key for f in submodules.attribute(sub.key, "FEEDS", ())],
                "sources": int(stats[0] or 0),
                "last_crawl": stats[1].isoformat() if stats[1] else None,
                "subscribed": sub.key in mine,
                "subscribers": subscribers,
                "modules": [sub.module],
                "parts": _parts(sub, content),
            }
        )
    return result


def sync_shared(db, sub: Submodule, content: Content) -> dict:
    """Make the sub-module's shared crawled sources match its page list. Retired ones are disabled. Flushes."""
    row = row_for(db, sub)
    existing = {s.key: s for s in db.query(KnowledgeSource).filter(KnowledgeSource.submodule_id == row.id)}
    counts = {"added": 0, "updated": 0, "retired": 0}
    for spec in content.sources:
        key = content.key_prefix + spec.key
        source = existing.pop(key, None)
        if source is None:
            source = KnowledgeSource(organization_id=None, submodule_id=row.id, key=key, enabled=True)
            db.add(source)
            counts["added"] += 1
        else:
            counts["updated"] += 1
        if source.url != spec.url:
            source.last_attempt_at = None
        source.url, source.category, source.public = spec.url, spec.category, False
        source.fetch_every_hours = spec.fetch_every_hours
        source.extractor = content.extractor_name(spec)
        source.enabled = True
        source.updated_at = utcnow()
    for source in existing.values():
        if source.enabled:
            source.enabled = False
            counts["retired"] += 1
    db.flush()
    return counts


def subscribe(db, org: Organization, name: object, actor: str | None = None) -> dict:
    """Turn the shared sub-modules of name on for the org, which writes the subscription rows, and bring their
    shared sources up to date. Commits.

    Returns the counts of the sync (added, updated, retired) and subscribed: true.
    """
    found = resolve(name)
    counts = {"added": 0, "updated": 0, "retired": 0}
    for sub in found:
        content = catalog.of(sub)
        if content is not None:
            counts = sync_shared(db, sub, content)
    organizations.set_modules(db, org, dict.fromkeys((s.key for s in found), True), actor=actor)
    logger.info("shared sub-module on org=%s name=%s %s", org.id, name, counts)
    return counts | {"subscribed": True}


def unsubscribe(db, org: Organization, name: object) -> dict:
    """Turn the shared sub-modules of name off. The shared sources stay for the other subscribers. Commits."""
    found = resolve(name)
    organizations.set_modules(db, org, dict.fromkeys((s.key for s in found), False))
    return {"subscribed": False}


def sync(db, org: Organization, name: object) -> dict:
    """Older name of subscribe(), for the sync routes and tools that clients still call."""
    return subscribe(db, org, name)


def overview(db) -> list[dict]:
    """Every shared sub-module row with its subscribers, shared pages, passages and failing pages, for the
    superadmin."""
    result = []
    for row in db.query(SharedContent).order_by(SharedContent.key).all():
        sources = db.query(KnowledgeSource).filter(KnowledgeSource.submodule_id == row.id)
        passages = (
            db.query(func.coalesce(func.sum(KnowledgeVersion.chunk_count), 0))
            .join(KnowledgeSource, KnowledgeSource.current_version_id == KnowledgeVersion.id)
            .filter(KnowledgeSource.submodule_id == row.id)
            .scalar()
        )
        failing = [
            {"key": s.key, "error": s.last_error} for s in sources.filter(KnowledgeSource.last_error.isnot(None))
        ]
        result.append(
            {
                "key": row.key,
                "title": row.title,
                "origin": row.origin,
                "status": row.status,
                "subscribers": db.query(SubmoduleSubscription).filter_by(submodule_id=row.id).count(),
                "sources": sources.filter(KnowledgeSource.enabled.is_(True)).count(),
                "passages": int(passages or 0),
                "failing": failing[:50],
            }
        )
    return result


def query_sources(name: object) -> list[dict]:
    return [
        {
            "key": q.key,
            "description": q.description,
            "params": [
                {
                    "name": p.name,
                    "description": p.description,
                    "required": p.required,
                    "example": p.example,
                    "choices": list(p.choices),
                    "many": p.many,
                }
                for p in q.params
            ],
        }
        for q in _content(name).queries
    ]


def _params(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise KnowledgeError("params must be an object of strings")
    out = {}
    for k, v in value.items():
        if isinstance(v, list):
            v = ",".join(str(x) for x in v)
        if not isinstance(v, str | int | float) or isinstance(v, bool) or len(str(v)) > 500:
            raise KnowledgeError(f"params.{k} must be a string of at most 500 characters")
        out[k] = str(v)
    return out


def query(db, org_id: int, org_prefix: str, name: object, source_key: Any, params: Any) -> dict:
    """Run a live query and return the cited URL and text. Queues indexing of the result when allowed."""
    content = _content(name)
    source = next((q for q in content.queries if q.key == source_key), None)
    if source is None:
        raise KnowledgeError(f"The shared content {content.name} has no live source named {source_key}", 404)
    read = None
    if source.signin is not None:
        signin = signins.SIGNINS.get(source.signin)
        if signin is None or not signin.usable(db, org_id):
            raise KnowledgeError(
                f"{source.key} needs the org's {source.signin} sign-in. An officer signs in on Explore, Shared", 409
            )
        read = partial(signin.read, db, org_id, org_prefix)
    try:
        with query_scope(db, org_id):
            if source.needs_search and not settings().search.base_url:
                raise KnowledgeError("Web search needs a SearXNG server. Set one on the Integrations page", 503)
            url, text = queries.run(source, _params(params), read)
    except QueryError as e:
        raise KnowledgeError(str(e), 422) from e
    except fetch.FetchRejected as e:
        raise KnowledgeError(str(e), 422) from e
    except fetch.FetchError as e:
        raise KnowledgeError(str(e), 502) from e
    limit = settings().scraper.query_max_chars
    text = text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0]
    if source.index and text.strip():
        defer(
            "submodules.index_result",
            org_id=org_id,
            org_prefix=org_prefix,
            submodule=content.name,
            query_key=source.key,
            url=url,
            text=text,
        )
    return {"submodule": content.name, "source": source.key, "url": url, "text": text}


def index_result(
    db, org_id: int, org_prefix: str, submodule: str, query_key: str, url: str, text: str, embedder: Embedder | None
) -> dict:
    """Index a live result as a source of the org, under <content>-live/. Commits.

    It never writes into a shared crawled source, which other orgs read.
    """
    owner = _content(submodule)
    digest = hashlib.sha256(url.encode()).hexdigest()[:10]
    key = f"{owner.live_prefix}{query_key}-{digest}"
    source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if source is None:
        category = next((q.category for q in owner.queries if q.key == query_key), "live")
        source = new_source(db, org_id, key=key, url=url, category=category, public=can_publish(db, org_prefix))
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    previous = db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first()
    if previous is not None and previous.content_hash == content_hash:
        db.commit()
        return {"key": source.key, "changed": False}
    title = f"{query_key.replace('_', ' ')}: {url}"
    result = crawl.index_text(db, source, text, title, content_hash, embedder, previous=previous, force=True)
    logger.info("live result indexed source=%s chunks=%s", source.key, result["chunks"])
    return result
