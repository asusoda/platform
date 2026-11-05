"""Library hours: the LibCal hours feed behind lib.asu.edu/hours, one line per location."""

from __future__ import annotations

import json

from modules.submodules.text import page_text
from modules.submodules.types import Fetched, Source

# The Arizona libraries on the ASU LibCal instance. lib.asu.edu/hours draws its table from this feed in the browser.
FEED = "https://api3.libcal.com/api_hours_grid.php?iid=1222&lid=0&format=json&weeks=1"


def extract_hours(fetched: Fetched) -> str:
    """The week's dates, then one line per location with each day's date and hours."""
    try:
        locations = json.loads(fetched.body)["locations"]
    except (ValueError, KeyError, TypeError):
        return page_text(fetched)
    names = {loc.get("lid"): loc.get("name", "") for loc in locations}
    out: list[str] = []
    for loc in locations:
        weeks = loc.get("weeks") or [{}]
        days = weeks[0]
        if not out and days:
            dates = [day.get("date", "") for day in days.values()]
            out.append(f"ASU Library hours for {dates[0]} to {dates[-1]}, Arizona time.")
        pairs = [
            f"{name} {day.get('date', '')} {day.get('rendered') or 'no hours listed'}" for name, day in days.items()
        ]
        name = loc.get("name", "")
        parent = names.get(loc.get("parent_lid"))
        label = f"{parent} > {name}" if parent else name
        if pairs:
            out.append(f"{label}: {'; '.join(pairs)}")
    return "\n".join(out)


SOURCE = Source(
    key="library_hours",
    url=FEED,
    category="library",
    fetch_every_hours=6,
    extractor=extract_hours,
)
