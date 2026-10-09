"""Scheduled auth housekeeping."""

from core.jobs import job
from modules.auth.tokens import token_manager


@job("auth.cleanup_tokens", cron="0 * * * *", audit=False)
def cleanup_tokens() -> None:
    """Delete expired refresh tokens. Runs hourly."""
    token_manager.cleanup_expired_refresh_tokens()
