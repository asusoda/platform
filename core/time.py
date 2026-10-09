"""Times as the database stores them: naive datetimes in UTC."""

import datetime
from typing import Any


def utcnow() -> datetime.datetime:
    """The current time in UTC, without tzinfo."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def iso(value: Any) -> str | None:
    """The ISO 8601 text of a datetime or date column value, or None."""
    return value.isoformat() if value else None
