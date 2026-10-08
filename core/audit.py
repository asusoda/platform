"""Audit log: a database row for every change made through the API and every job with side effects.

API writes are recorded after the response by core/audit_http.py (POST, PUT, PATCH, DELETE with a
status below 400). Request bodies are not stored. This file has no Flask, so services can record. Jobs record their runs from core/jobs.py. Rows older
than AUDIT_RETENTION_DAYS (default 365) are deleted daily by the audit.prune job.
"""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import JSON, Column, DateTime, Integer, String

from core.base import Base
from core.db import session
from core.jobs import job
from core.logging_config import get_logger

logger = get_logger("audit")


class AuditEntry(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    source = Column(String(20), nullable=False)  # api, job, bot
    action = Column(String(255), nullable=False)  # "PUT /api/organizations/<int:org_id>/modules", "job points.x"
    org = Column(String(100), nullable=True, index=True)  # org prefix
    actor_kind = Column(String(20), nullable=True)  # access, session, app, clerk, job
    actor_id = Column(String(255), nullable=True)  # Discord id, member email, or job name
    status = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source": self.source,
            "action": self.action,
            "org": self.org,
            "actor_kind": self.actor_kind,
            "actor_id": self.actor_id,
            "status": self.status,
            "details": self.details,
        }


def record(
    action: str,
    *,
    source: str,
    org: str | None = None,
    actor_kind: str | None = None,
    actor_id: str | None = None,
    status: int | None = None,
    details: dict | None = None,
) -> None:
    """Write one audit row in its own transaction. Never raises: a failed audit write is logged."""
    try:
        with session() as db:
            db.add(
                AuditEntry(
                    source=source,
                    action=action[:255],
                    org=org,
                    actor_kind=actor_kind,
                    actor_id=actor_id,
                    status=status,
                    details=details,
                )
            )
    except Exception:
        logger.exception("audit write failed action=%s", action)


def list_entries(db, *, org: str | None = None, limit: int = 100, before_id: int | None = None) -> list[dict]:
    """Newest first. Page with before_id = the last id of the previous page."""
    query = db.query(AuditEntry)
    if org is not None:
        query = query.filter(AuditEntry.org == org)
    if before_id is not None:
        query = query.filter(AuditEntry.id < before_id)
    rows = query.order_by(AuditEntry.id.desc()).limit(max(1, min(limit, 500))).all()
    return [row.to_dict() for row in rows]


RETENTION_DAYS = int(os.environ.get("AUDIT_RETENTION_DAYS", "365"))


@job("audit.prune", cron="30 3 * * *", audit=False)
def prune() -> None:
    """Delete audit rows older than AUDIT_RETENTION_DAYS."""
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    with session() as db:
        deleted = db.query(AuditEntry).filter(AuditEntry.created_at < cutoff).delete()
    logger.info("audit pruned rows=%s", deleted)
