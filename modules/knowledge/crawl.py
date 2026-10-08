"""Crawled sources: the platform fetches a URL on a schedule, extracts, chunks, embeds and indexes it.

A run is skipped after
the fetch when the page hash is unchanged, and refused when the extracted text shrank below half
of the last indexed version, so a broken page cannot wipe a good index. No Flask here.
"""

import datetime
import hashlib
import os
from typing import Any, cast

from sqlalchemy import or_

from core.log import get_logger
from core.time import utcnow
from modules.knowledge import extract, fetch, runs, settings
from modules.knowledge.embedder import Embedder
from modules.knowledge.models import KnowledgeSource, KnowledgeVersion
from modules.knowledge.service import (
    KEY_PATTERN,
    MAX_CHUNKS,
    KnowledgeError,
    _embed,
    _find,
    _source_dict,
    _text,
    _write_version,
    can_publish,
)

logger = get_logger("knowledge.crawl")

MAX_EVERY_HOURS = 24 * 30
QUALITY_FLOOR_RATIO = 0.5
QUALITY_FLOOR_MIN_CHARS = 500


def _setting(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


def schedule(db, org_id: int, org_prefix: str, key: str, data: dict) -> dict:
    """Create or update a crawled source from untrusted input. Commits."""
    if not isinstance(key, str) or not KEY_PATTERN.match(key):
        raise KnowledgeError("key must be 1 to 255 letters, digits or ._:/- and start with a letter or digit")
    url = _text(data.get("url"), "url", 2000) or ""
    if not url.startswith(("https://", "http://")):
        raise KnowledgeError("url must start with http:// or https://")
    category = _text(data.get("category"), "category", 100)
    title = _text(data.get("title"), "title", 500, required=False)
    every = data.get("fetch_every_hours", 24)
    if not isinstance(every, int) or isinstance(every, bool) or not 1 <= every <= MAX_EVERY_HOURS:
        raise KnowledgeError(f"fetch_every_hours must be an integer from 1 to {MAX_EVERY_HOURS}")
    public, enabled = data.get("public", False), data.get("enabled", True)
    if not isinstance(public, bool) or not isinstance(enabled, bool):
        raise KnowledgeError("public and enabled must be true or false")
    if public and not can_publish(org_prefix):
        raise KnowledgeError("This organization may not write public sources", 403)

    source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if source is None:
        source = KnowledgeSource(organization_id=org_id, key=key)
        db.add(source)
    if source.url != url:
        source.last_attempt_at = None  # a new URL is due at once
    source.url, source.category, source.public, source.enabled = url, category, public, enabled
    source.title = title or source.title
    source.fetch_every_hours = every
    source.updated_at = utcnow()
    db.commit()
    return _source_dict(source, db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first())


def run(db, org_id: int, key: str, embedder: Embedder | None, force: bool = False) -> dict:
    """Crawl one source of the org now. Commits."""
    source = _find(db, org_id, key)
    if source.fetch_every_hours is None:
        raise KnowledgeError("This source is written by a client, not crawled", 409)
    return crawl(db, source, embedder, force=force)


def queue(db, org_id: int, org_prefix: str, key: str, force: bool = False) -> None:
    """Start the crawl job for one source of the org. The result shows on the source as last_attempt_at and last_error."""
    from core.jobs import defer

    source = _find(db, org_id, key)
    if source.fetch_every_hours is None:
        raise KnowledgeError("This source is written by a client, not crawled", 409)
    defer("knowledge.crawl_source", org_id=org_id, key=key, force=force, org_prefix=org_prefix)


def crawl(db, source: KnowledgeSource, embedder: Embedder | None, *, force: bool = False, pacer: Any = None) -> dict:
    """Fetch, extract, chunk, embed and index one crawled source. Commits; records any error on the source."""
    started = runs.Timer()
    source.last_attempt_at = utcnow()
    db.commit()
    try:
        result = _crawl(db, source, embedder, force=force, pacer=pacer)
    except (fetch.FetchError, fetch.FetchRejected, KnowledgeError) as e:
        db.rollback()
        source.last_error = str(e.message if isinstance(e, KnowledgeError) else e)[:1000]
        runs.record(db, cast(int, source.organization_id), str(source.key), "crawl", started, error=source.last_error)
        db.commit()
        logger.warning("crawl failed source=%s error=%s", source.key, source.last_error)
        return {"key": source.key, "changed": False, "error": source.last_error}
    source.last_error = None
    runs.record(
        db,
        cast(int, source.organization_id),
        str(source.key),
        "crawl",
        started,
        changed=result["changed"],
        chunks=result["chunks"],
    )
    db.commit()
    logger.info("crawled source=%s changed=%s chunks=%s", source.key, result["changed"], result["chunks"])
    return result


def _crawl(db, source: KnowledgeSource, embedder: Embedder | None, *, force: bool, pacer: Any) -> dict:
    url = str(source.url)
    if pacer is not None:
        pacer.wait(url)
    page = fetch.fetch(url)
    content_hash = hashlib.sha256(page.body).hexdigest()
    previous = db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first()
    if previous is not None and previous.content_hash == content_hash and not force:
        return {"key": source.key, "changed": False, "chunks": int(previous.chunk_count or 0)}

    custom = extract.extractor(cast(str | None, source.extractor))
    if custom is not None:
        text = custom(page)
        title = page.title or (extract.title_of(page.body) if page.text is None else None)
    elif page.text is not None:
        text, title = page.text, page.title
    else:
        text, title = extract.extract_text(page.body), extract.title_of(page.body)
    return index_text(db, source, text, title, content_hash, embedder, previous=previous, force=force)


def index_text(
    db,
    source: KnowledgeSource,
    text: str,
    title: str | None,
    content_hash: str,
    embedder: Embedder | None,
    *,
    previous: KnowledgeVersion | None = None,
    force: bool = False,
) -> dict:
    """Chunk, embed and store text as the source's new version. Commits."""
    label: str = title or cast(str | None, source.title) or str(source.key)
    tuning = settings.for_org(db, cast(int, source.organization_id))
    pieces = extract.chunk_text(text, max_chars=tuning["chunk_chars"], overlap_chars=tuning["chunk_overlap"])
    if not pieces:
        raise KnowledgeError("No text was extracted; the index is kept")
    if len(pieces) > MAX_CHUNKS:
        raise KnowledgeError(f"The text makes {len(pieces)} passages, more than {MAX_CHUNKS}; the index is kept")
    floor = cast(int | None, previous.text_chars) if previous is not None else None
    if not force and floor is not None and floor >= QUALITY_FLOOR_MIN_CHARS:
        if len(text) < int(floor * QUALITY_FLOOR_RATIO):
            raise KnowledgeError(
                f"Extracted {len(text)} characters against {floor} last time; the index is kept. Run with force to accept"
            )

    # Each chunk carries the page title
    rows: list[dict] = [
        {"ordinal": i, "level": 0, "parent_ordinal": None, "content": f"{label}\n{piece}", "embedding": None}
        for i, piece in enumerate(pieces)
    ]
    model = _embed(rows, embedder)
    source.title = label[:500]
    _write_version(db, source, rows, content_hash, model, text_chars=len(text))
    db.commit()
    return {"key": source.key, "changed": True, "chunks": len(rows)}


def due(db, now: datetime.datetime | None = None, limit: int = 20) -> list[KnowledgeSource]:
    """Enabled crawled sources whose schedule has come round, never-tried ones first."""
    now = now or utcnow()
    candidates = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.fetch_every_hours.isnot(None), KnowledgeSource.enabled.is_(True))
        .filter(or_(KnowledgeSource.last_attempt_at.is_(None), KnowledgeSource.last_attempt_at < now))
        .order_by(KnowledgeSource.last_attempt_at.is_(None).desc(), KnowledgeSource.last_attempt_at)
        .all()
    )
    ready = [
        s
        for s in candidates
        if s.last_attempt_at is None or s.last_attempt_at + datetime.timedelta(hours=int(s.fetch_every_hours)) <= now
    ]
    return ready[:limit]


def crawl_due(db, embedder: Embedder | None, now: datetime.datetime | None = None) -> dict:
    """Crawl every due source, one host at a time per KNOWLEDGE_CRAWL_GAP_SECONDS. Commits."""
    pacer = fetch.HostPacer(_setting("KNOWLEDGE_CRAWL_GAP_SECONDS", 2))
    results = []
    for source in due(db, now, limit=_setting("KNOWLEDGE_CRAWL_BATCH", 20)):
        started = runs.Timer()
        try:
            results.append(crawl(db, source, embedder, pacer=pacer))
        except Exception:
            # One broken source must not stop the rest of the batch
            db.rollback()
            logger.exception("crawl crashed source=%s", source.key)
            runs.record(
                db,
                cast(int, source.organization_id),
                str(source.key),
                "crawl",
                started,
                error="The crawl crashed. The server log has the details",
            )
            db.commit()
            results.append({"key": source.key, "error": "crashed"})
    return {
        "crawled": len(results),
        "changed": sum(1 for r in results if r.get("changed")),
        "failed": sum(1 for r in results if r.get("error")),
    }


def reindex(db, org_id: int, embedder: Embedder | None) -> dict:
    """Crawl every crawled source of the org with force, one host at a time. Commits."""
    pacer = fetch.HostPacer(_setting("KNOWLEDGE_CRAWL_GAP_SECONDS", 2))
    sources = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.organization_id == org_id, KnowledgeSource.fetch_every_hours.isnot(None))
        .order_by(KnowledgeSource.key)
        .all()
    )
    results = [crawl(db, source, embedder, force=True, pacer=pacer) for source in sources]
    return {"crawled": len(results), "failed": sum(1 for r in results if r.get("error"))}
