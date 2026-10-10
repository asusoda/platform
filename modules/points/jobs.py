"""Points jobs."""

from core.jobs import job


@job("points.import_event_csv")
def import_event_csv(file_content: str, event_name: str, event_points: int, org_prefix: str) -> None:
    """Award event points to everyone checked in on an uploaded attendance CSV."""
    from modules.points.api import process_csv_in_background

    process_csv_in_background(file_content, event_name, event_points, org_prefix)
