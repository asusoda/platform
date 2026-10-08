"""Calendar jobs."""

import os

from core.jobs import job

# Calendar sync is not scheduled unless CALENDAR_SYNC_CRON is set (for example "0 */2 * * *"),
# because it writes to every enabled org's Google Calendar.
SYNC_CRON = os.environ.get("CALENDAR_SYNC_CRON") or None


@job("calendar.sync_all", cron=SYNC_CRON, retry=2)
def sync_all() -> None:
    """Sync every active org with calendar sync turned on."""
    from modules.calendar import service

    service.sync_all()
