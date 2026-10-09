"""The log of crawls and uploads: one row per attempt, kept for the latest RUNS_KEPT of each org. No Flask here."""

import time

from core import webhooks
from core.time import iso, utcnow
from modules.knowledge.models import KnowledgeRun

RUNS_KEPT = 500
MAX_LIST = 200

webhooks.declare("knowledge.crawl_failed", "Knowledge crawl failures", "A crawl of a knowledge source fails.")


class Timer:
    """The start of a run, as wall time and as a monotonic clock."""

    def __init__(self) -> None:
        self.at = utcnow()
        self._clock = time.monotonic()

    def ms(self) -> int:
        return int((time.monotonic() - self._clock) * 1000)


def record(
    db,
    org_id: int,
    source_key: str,
    kind: str,
    started: Timer,
    *,
    changed: bool = False,
    chunks: int | None = None,
    error: str | None = None,
) -> None:
    """Add a run for the source and drop the org's runs past RUNS_KEPT. Flushes, does not commit."""
    db.add(
        KnowledgeRun(
            organization_id=org_id,
            source_key=source_key,
            kind=kind,
            started_at=started.at,
            duration_ms=started.ms(),
            changed=changed,
            chunks=chunks,
            error=error[:1000] if error else None,
        )
    )
    db.flush()
    if kind == "crawl" and error:
        message = webhooks.Message(
            title=f"Crawl of {source_key} failed", text=error[:1000], color=webhooks.RED, footer="Knowledge"
        )
        webhooks.emit(org_id, "knowledge.crawl_failed", message)
    oldest_kept = (
        db.query(KnowledgeRun.id)
        .filter_by(organization_id=org_id)
        .order_by(KnowledgeRun.id.desc())
        .offset(RUNS_KEPT - 1)
        .limit(1)
        .scalar()
    )
    if oldest_kept is not None:
        db.query(KnowledgeRun).filter(KnowledgeRun.organization_id == org_id, KnowledgeRun.id < oldest_kept).delete(
            synchronize_session=False
        )


def recent(db, org_id: int, limit: object = None, failed_only: bool = False) -> list[dict]:
    """The org's latest runs, newest first."""
    count = limit if isinstance(limit, int) and not isinstance(limit, bool) and 0 < limit <= MAX_LIST else 50
    query = db.query(KnowledgeRun).filter_by(organization_id=org_id)
    if failed_only:
        query = query.filter(KnowledgeRun.error.isnot(None))
    return [
        {
            "id": run.id,
            "source_key": run.source_key,
            "kind": run.kind,
            "started_at": iso(run.started_at),
            "duration_ms": run.duration_ms,
            "changed": bool(run.changed),
            "chunks": run.chunks,
            "error": run.error,
        }
        for run in query.order_by(KnowledgeRun.id.desc()).limit(count).all()
    ]
