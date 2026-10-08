"""Indexing live ASU query results. Importing this module also registers the ASU extractors."""

from core.db import db_connect
from core.jobs import job
from modules.asu import service as _service  # noqa: F401  registers extractors


@job("asu.index_result", audit=False)
def index_result(org_id: int, org_prefix: str, query_key: str, url: str, text: str) -> None:
    """Write a live query result into the org's knowledge after the caller has its answer."""
    from modules.asu import service
    from modules.knowledge import embedder

    db = db_connect.SessionLocal()
    try:
        service.index_result(db, org_id, org_prefix, query_key, url, text, embedder.for_org(db, org_id))
    finally:
        db.close()
