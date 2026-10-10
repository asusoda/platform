"""Points jobs."""

from core.cache import cache
from core.jobs import job
from modules.points.csv_import import process_csv_in_background


@job("points.import_event_csv")
def import_event_csv(file_content: str, event_name: str, event_points: int, org_prefix: str) -> None:
    """Award event points to everyone checked in on an uploaded attendance CSV."""
    process_csv_in_background(file_content, event_name, event_points, org_prefix)
    cache.invalidate("org")
