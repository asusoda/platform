"""Crawling scheduled knowledge sources."""

from core.db import db_connect
from core.jobs import job


@job("knowledge.crawl_due", cron="*/10 * * * *", audit=False)
def crawl_due() -> None:
    """Crawl every enabled source whose fetch_every_hours has passed since its last attempt."""
    from modules.knowledge import crawl, embedder

    db = db_connect.SessionLocal()
    try:
        result = crawl.crawl_due(db, embedder.configured())
        if result["crawled"]:
            crawl.logger.info("crawl run %s", result)
    finally:
        db.close()


@job("knowledge.crawl_source")
def crawl_source(org_id: int, key: str, force: bool = False, org_prefix: str | None = None) -> None:
    """Crawl one source now, on request."""
    from modules.knowledge import crawl, embedder

    db = db_connect.SessionLocal()
    try:
        crawl.run(db, org_id, key, embedder.configured(), force=force)
    finally:
        db.close()
