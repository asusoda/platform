"""Deployment health checks."""

from core.db import db_connect
from core.jobs import job


@job("runpod.check_deployments", cron="* * * * *", audit=False)
def check_deployments() -> None:
    """Mark running app deployments healthy or failed from their health path."""
    from hosting import deploys

    db = db_connect.SessionLocal()
    try:
        result = deploys.check_deployments(db)
        if result["healthy"] or result["failed"]:
            deploys.logger.info("deployments checked %s", result)
    finally:
        db.close()
