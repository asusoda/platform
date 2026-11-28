"""Points jobs."""

from core.jobs import job
from modules.points.csv_import import process_csv_in_background


@job("points.import_event_csv", once=("import_id",))
def import_event_csv(
    file_content: str, event_name: str, event_points: int, org_prefix: str, import_id: int | None = None
) -> None:
    """Award event points to everyone checked in on an uploaded attendance CSV.

    A job queued before the import runs existed has no import_id and runs with no run row.
    """
    process_csv_in_background(file_content, event_name, event_points, org_prefix, import_id)
