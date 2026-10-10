"""ASU sources for the knowledge module: the scheduled page list and live queries. No Flask here.

Ported from SparkyAI's scraper (apps/scraper/sources and apps/scraper/query). sync() registers
every ASU page as a crawled knowledge source of an org, under keys starting with asu/. Live
queries fetch one page or API with parameters, answer the caller, and then index what they read,
where the source allows it. Pages behind an ASU sign-in are not ported.
"""

import hashlib
from typing import Any

from core.jobs import defer
from core.logging_config import get_logger
from modules.asu import registry
from modules.asu.settings import settings
from modules.asu.sources import SOURCES
from modules.asu.types import QueryError
from modules.knowledge import crawl, extractors, fetch
from modules.knowledge.embedder import Embedder
from modules.knowledge.models import KnowledgeSource, KnowledgeVersion
from modules.knowledge.service import KnowledgeError, can_publish

logger = get_logger("asu")

KEY_PREFIX = "asu/"
LIVE_PREFIX = "asu-live/"

for _source in SOURCES.values():
    if _source.extractor is not None:
        extractors.register(f"asu.{_source.key}", _source.extractor)


def sync(db, org_id: int, org_prefix: str) -> dict:
    """Make the org's asu/ crawled sources match the ASU source list. Retired ones are disabled. Commits."""
    public = can_publish(org_prefix)
    existing = {
        s.key: s
        for s in db.query(KnowledgeSource).filter(
            KnowledgeSource.organization_id == org_id, KnowledgeSource.key.like(KEY_PREFIX + "%")
        )
    }
    counts = {"added": 0, "updated": 0, "retired": 0}
    for spec in SOURCES.values():
        key = KEY_PREFIX + spec.key
        source = existing.pop(key, None)
        if source is None:
            source = KnowledgeSource(organization_id=org_id, key=key, enabled=True)
            db.add(source)
            counts["added"] += 1
        else:
            counts["updated"] += 1
        if source.url != spec.url:
            source.last_attempt_at = None
        source.url, source.category, source.public = spec.url, spec.category, public
        source.fetch_every_hours = spec.fetch_every_hours
        source.extractor = f"asu.{spec.key}" if spec.extractor is not None else None
    for source in existing.values():
        if source.enabled:
            source.enabled = False
            counts["retired"] += 1
    db.commit()
    return counts


def query_sources() -> list[dict]:
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
        for q in registry.QUERY_SOURCES.values()
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


def query(db, org_id: int, org_prefix: str, source_key: Any, params: Any) -> dict:
    """Run a live query and return the cited URL and text. Queues indexing of the result when allowed."""
    source = registry.QUERY_SOURCES.get(source_key) if isinstance(source_key, str) else None
    if source is None:
        raise KnowledgeError(f"No live source named {source_key}", 404)
    if source.key == "web" and not settings().search.base_url:
        raise KnowledgeError("Web search needs SEARXNG_URL", 503)
    try:
        url, text = registry.run(source, _params(params))
    except QueryError as e:
        raise KnowledgeError(str(e), 422) from e
    except fetch.FetchRejected as e:
        raise KnowledgeError(str(e), 422) from e
    except fetch.FetchError as e:
        raise KnowledgeError(str(e), 502) from e
    limit = settings().scraper.query_max_chars
    text = text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0]
    if source.index and text.strip():
        defer("asu.index_result", org_id=org_id, org_prefix=org_prefix, query_key=source.key, url=url, text=text)
    return {"source": source.key, "url": url, "text": text}


def index_result(db, org_id: int, org_prefix: str, query_key: str, url: str, text: str, embedder: Embedder | None):
    """Index a live result: under the scheduled source with the same URL, else its own source. Commits."""
    spec = next((s for s in SOURCES.values() if s.url == url), None)
    source = None
    if spec is not None:
        source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=KEY_PREFIX + spec.key).first()
    if source is None:
        digest = hashlib.sha256(url.encode()).hexdigest()[:10]
        key = f"{LIVE_PREFIX}{query_key}-{digest}"
        source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
        if source is None:
            category = registry.QUERY_SOURCES[query_key].category
            source = KnowledgeSource(
                organization_id=org_id, key=key, url=url, category=category, public=can_publish(org_prefix)
            )
            db.add(source)
            db.flush()
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    previous = db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first()
    if previous is not None and previous.content_hash == content_hash:
        db.commit()
        return {"key": source.key, "changed": False}
    title = f"{query_key.replace('_', ' ')}: {url}"
    result = crawl.index_text(db, source, text, title, content_hash, embedder, previous=previous, force=True)
    logger.info("live result indexed source=%s chunks=%s", source.key, result["chunks"])
    return result
