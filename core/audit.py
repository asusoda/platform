"""Audit log: a database row for every change made through the API and every job with side effects.

API writes are recorded automatically after the response (POST, PUT, PATCH, DELETE with a status
below 400). Request bodies are not stored. Jobs record their runs from core/jobs.py. Rows older
than AUDIT_RETENTION_DAYS (default 365) are deleted daily by the audit.prune job.
"""

import os
from datetime import UTC, datetime, timedelta

from flask import Flask, request
from sqlalchemy import JSON, Column, DateTime, Integer, String, text

from core.base import Base
from core.jobs import job
from core.logging_config import get_logger
from core.request_log import _credential, _org

logger = get_logger("audit")

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Writes that are too frequent or carry nothing worth keeping
SKIPPED_ROUTES = {"/api/auth/refresh"}
# Reads that change state
AUDITED_READS = {"/api/auth/appToken"}


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


def _session():
    from shared import db_connect

    return db_connect.SessionLocal()


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
    db = _session()
    try:
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
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("audit write failed action=%s", action)
    finally:
        db.close()


def list_entries(db, *, org: str | None = None, limit: int = 100, before_id: int | None = None) -> list[dict]:
    """Newest first. Page with before_id = the last id of the previous page."""
    query = db.query(AuditEntry)
    if org is not None:
        query = query.filter(AuditEntry.org == org)
    if before_id is not None:
        query = query.filter(AuditEntry.id < before_id)
    rows = query.order_by(AuditEntry.id.desc()).limit(max(1, min(limit, 500))).all()
    return [row.to_dict() for row in rows]


def _org_prefix(db) -> str | None:
    """The org the request names, as a prefix (routes use either a prefix or a numeric id)."""
    args = request.view_args or {}
    if "org_prefix" in args:
        return str(args["org_prefix"])
    if "org_id" in args:
        row = db.execute(text("SELECT prefix FROM organizations WHERE id = :id"), {"id": args["org_id"]}).first()
        return row[0] if row else str(args["org_id"])
    return _org()


def _actor(token_manager) -> tuple[str | None, str | None]:
    kind, discord_id = _credential(token_manager)
    if discord_id:
        return kind, str(discord_id)
    email = getattr(request, "clerk_user_email", None)
    if email:
        return "clerk", email
    return kind, None


def register_audit(app: Flask, token_manager) -> None:
    """Record every successful API write."""

    @app.after_request
    def _audit_request(response):
        rule = request.url_rule.rule if request.url_rule else None
        audited = request.method in WRITE_METHODS or rule in AUDITED_READS
        if not rule or not audited or rule in SKIPPED_ROUTES or not rule.startswith("/api/"):
            return response
        if response.status_code >= 400:
            return response
        try:
            db = _session()
            try:
                org = _org_prefix(db)
            finally:
                db.close()
            kind, actor_id = _actor(token_manager)
            record(
                f"{request.method} {rule}",
                source="api",
                org=org,
                actor_kind=kind,
                actor_id=actor_id,
                status=response.status_code,
                details={"path": request.path},
            )
        except Exception:
            logger.exception("audit hook failed")
        return response


RETENTION_DAYS = int(os.environ.get("AUDIT_RETENTION_DAYS", "365"))


@job("audit.prune", cron="30 3 * * *", audit=False)
def prune() -> None:
    """Delete audit rows older than AUDIT_RETENTION_DAYS."""
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    db = _session()
    try:
        deleted = db.query(AuditEntry).filter(AuditEntry.created_at < cutoff).delete()
        db.commit()
        logger.info("audit pruned rows=%s", deleted)
    finally:
        db.close()
