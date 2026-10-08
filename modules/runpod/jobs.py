"""Deployment health checks."""

from core.jobs import job


@job("runpod.check_deployments", cron="* * * * *", audit=False)
def check_deployments() -> None:
    """Mark running app deployments healthy or failed from their health path."""
    from modules.runpod import service
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        result = service.check_deployments(db)
        if result["healthy"] or result["failed"]:
            service.logger.info("deployments checked %s", result)
    finally:
        db.close()
