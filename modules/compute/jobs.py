"""Starts and stops pods for their scheduled sessions."""

from core.jobs import job


@job("compute.schedule", cron="*/5 * * * *", audit=False)
def schedule() -> None:
    """Start pods before their sessions and stop them after."""
    from modules.compute import schedule as sessions
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        sessions.run(db)
    finally:
        db.close()
