"""Crawling scheduled knowledge sources, and indexing live query results."""

from core.db import db_connect
from core.jobs import job


@job("knowledge.crawl_due", cron="*/10 * * * *", audit=False, once=())
def crawl_due() -> None:
    """Crawl every enabled source whose fetch_every_hours has passed since its last attempt."""
    from modules.knowledge import crawl, embedder

    db = db_connect.SessionLocal()
    try:
        result = crawl.crawl_due(
            db, lambda org_id: embedder.for_org(db, org_id) if org_id is not None else embedder.configured()
        )
        if result["crawled"]:
            crawl.logger.info("crawl run %s", result)
    finally:
        db.close()


@job("knowledge.crawl_source", once=("org_id", "key"))
def crawl_source(org_id: int, key: str, force: bool = False, org_prefix: str | None = None) -> None:
    """Crawl one source now, on request."""
    from modules.knowledge import crawl, embedder

    db = db_connect.SessionLocal()
    try:
        crawl.run(db, org_id, key, embedder.for_org(db, org_id), force=force)
    finally:
        db.close()


@job("knowledge.reindex", once=("org_id",))
def reindex(org_id: int) -> None:
    """Crawl every crawled source of the org again with force, so new chunk settings apply."""
    from modules.knowledge import crawl, embedder

    db = db_connect.SessionLocal()
    try:
        result = crawl.reindex(db, org_id, embedder.for_org(db, org_id))
        crawl.logger.info("reindex org=%s %s", org_id, result)
    finally:
        db.close()


@job("knowledge.reembed", once=("org_id",))
def reembed(org_id: int, org_prefix: str | None = None) -> None:
    """Embed every passage of the org that is not on the org's current embedding model."""
    from modules.knowledge import embedder, reembed

    db = db_connect.SessionLocal()
    try:
        result = reembed.run(db, org_id, embedder.for_org(db, org_id))
        reembed.logger.info("re-embed org=%s %s", org_id, result)
    finally:
        db.close()


@job("submodules.index_result", audit=False)
def index_result(org_id: int, org_prefix: str, submodule: str, query_key: str, url: str, text: str) -> None:
    """Write a live query result into the org's knowledge after the caller has its answer."""
    from modules.knowledge import embedder, shared

    db = db_connect.SessionLocal()
    try:
        shared.index_result(db, org_id, org_prefix, submodule, query_key, url, text, embedder.for_org(db, org_id))
    finally:
        db.close()
