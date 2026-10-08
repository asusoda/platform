"""Agent data retention."""

from core.jobs import job


@job("agents.prune", cron="15 4 * * *")
def prune() -> None:
    """Delete conversations idle for AGENT_RETENTION_DAYS (default 180), expired memories and old pending actions."""
    from core.logging_config import get_logger
    from modules.agents import service
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        get_logger("agents").info("agents pruned %s", service.prune(db))
    finally:
        db.close()
