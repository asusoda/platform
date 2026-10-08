"""Connected account housekeeping."""

from core.jobs import job


@job("accounts.prune", cron="40 * * * *")
def prune() -> None:
    """Delete account logins past their expiry."""
    from core.logging_config import get_logger
    from modules.accounts import service
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        get_logger("accounts").info("accounts pruned %s", service.prune(db))
    finally:
        db.close()
