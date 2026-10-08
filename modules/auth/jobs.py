"""Scheduled auth housekeeping."""

from core.jobs import job


@job("auth.cleanup_tokens", cron="0 * * * *")
def cleanup_tokens() -> None:
    """Delete expired refresh tokens. Runs hourly."""
    from shared import tokenManager

    tokenManager.cleanup_expired_refresh_tokens()
