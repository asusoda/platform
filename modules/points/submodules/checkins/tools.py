"""Check-in tools."""

from core.tools import tool
from modules.points.submodules.checkins import csv_import
from modules.points.tools import EVENT

MAX_CSV = 2_000_000


@tool(
    "points.import_csv",
    description=(
        "Give event_points to each checked-in row of an attendance CSV, once per email, in the background. "
        "A row with no member makes one. points.imports shows the progress and the errors of the run."
    ),
    scope="points:write",
    module="points.checkins",
    input_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "minLength": 1, "maxLength": MAX_CSV},
            "event_name": EVENT,
            "event_points": {"type": "integer", "minimum": -100000, "maximum": 100000},
        },
        "required": ["content", "event_name", "event_points"],
        "additionalProperties": False,
    },
)
def points_import_csv(db, org, caller, content: str, event_name: str, event_points: int):
    run = csv_import.queue(db, org, content, event_name, event_points, caller.actor)
    return {"queued": True, "import_id": run.id}
