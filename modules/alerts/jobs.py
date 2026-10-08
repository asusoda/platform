"""Running alert feeds on their schedules and on request."""

from core.jobs import job


@job("alerts.run_due", cron="*/15 * * * *", audit=False)
def run_due() -> None:
    """Run every enabled feed whose every_hours has passed since its last run."""
    from modules.alerts import service
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        service.run_due(db)
    finally:
        db.close()


@job("alerts.run_feed")
def run_feed(org_id: int, key: str, post_existing: bool = False) -> None:
    """Run one feed now, on request."""
    from modules.alerts import service
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        service.run_now(db, org_id, key, post_existing=post_existing)
    finally:
        db.close()
