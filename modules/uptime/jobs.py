"""Uptime checks on a schedule, and the daily removal of old checks."""

from core.db import db_connect
from core.jobs import job


@job("uptime.check_due", cron="* * * * *", audit=False)
def check_due() -> None:
    """Check every enabled monitor whose interval has passed."""
    from modules.uptime import service

    db = db_connect.SessionLocal()
    try:
        service.check_due(db)
    finally:
        db.close()


@job("uptime.prune", cron="50 3 * * *")
def prune() -> None:
    """Delete checks older than UPTIME_RETENTION_DAYS (default 30)."""
    from modules.uptime import service

    db = db_connect.SessionLocal()
    try:
        service.prune(db)
    finally:
        db.close()
