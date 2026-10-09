"""ASU term codes and Arizona dates and times for the ASU queries."""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from modules.packs.types import QueryError

#: Arizona keeps UTC-7 all year.
ARIZONA = ZoneInfo("America/Phoenix")

# ASU term codes are 2 plus the two-digit calendar year plus the session digit; Fall 2026 is 2267.
_TERM_DIGIT = {"spring": "1", "summer": "4", "fall": "7"}


def term_code(term: str) -> str:
    """Fall 2026 to 2267. Raises QueryError on anything else."""
    parts = term.strip().split()
    if len(parts) != 2:
        raise QueryError(f"term must look like 'Fall 2026', got {term!r}")
    season, year = parts[0].lower(), parts[1]
    if season not in _TERM_DIGIT:
        raise QueryError(f"term season must be spring, summer or fall, got {parts[0]!r}")
    if not (year.isdigit() and len(year) == 4):
        raise QueryError(f"term year must be four digits, got {year!r}")
    return f"2{year[2:]}{_TERM_DIGIT[season]}"


def day(moment: datetime.datetime) -> str:
    """A moment as the Arizona date it falls on, like Sat Sep 12, 2026."""
    return moment.astimezone(ARIZONA).strftime("%a %b %d, %Y")


def clock(moment: datetime.datetime) -> str:
    """A moment as the Arizona time it falls on, like 3:05 PM."""
    return moment.astimezone(ARIZONA).strftime("%I:%M %p").lstrip("0")
