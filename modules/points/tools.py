"""Points tools."""

from core.tools import tool
from modules.points import service
from modules.points.submodules.checkins import csv_import

MEMBER = {"type": "string", "minLength": 1, "maxLength": 255, "description": "Email, uuid, username or Discord id"}
EVENT = {"type": "string", "minLength": 1, "maxLength": 255}
ENTRY_IDS = {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": service.MAX_IDS}


@tool(
    "points.entries",
    description="The org's point entries, newest first: points, event, member id and who gave them.",
    scope="members:read",
    module="points",
    input_schema={
        "type": "object",
        "properties": {
            "event": EVENT,
            "limit": {"type": "integer", "minimum": 1, "maximum": service.MAX_ENTRIES},
        },
        "additionalProperties": False,
    },
)
def points_entries(db, org, caller, event: str | None = None, limit: int = 200):
    return {"entries": service.entries(db, int(org.id), event, limit)}


@tool(
    "points.history",
    description="One member's total points and point entries in the org.",
    scope="members:read",
    module="points",
    input_schema={
        "type": "object",
        "properties": {"member": MEMBER},
        "required": ["member"],
        "additionalProperties": False,
    },
)
def points_history(db, org, caller, member: str):
    return service.member_history(db, int(org.id), member)


@tool(
    "points.award",
    description=(
        "Give the same points to 1 to 100 members, for an event. A negative value takes points away. "
        "If one member is not in the org, nothing changes."
    ),
    scope="points:write",
    module="points",
    input_schema={
        "type": "object",
        "properties": {
            "members": {"type": "array", "items": MEMBER, "minItems": 1, "maxItems": service.MAX_IDS},
            "points": {"type": "number", "minimum": -100000, "maximum": 100000},
            "event": EVENT,
        },
        "required": ["members", "points"],
        "additionalProperties": False,
    },
)
def points_award(db, org, caller, members: list[str], points: float, event: str | None = None):
    return {"entries": service.award(db, int(org.id), list(dict.fromkeys(members)), points, event, caller.actor)}


def _delete_preview(db, org, caller, ids: list[int] | None = None, event: str | None = None):
    return service.delete_preview(db, int(org.id), ids, event)


@tool(
    "points.delete",
    description="Delete point entries by id (up to 100), or every entry of one event.",
    scope="points:write",
    module="points",
    preview=_delete_preview,
    input_schema={
        "type": "object",
        "properties": {"ids": ENTRY_IDS, "event": EVENT},
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def points_delete(db, org, caller, ids: list[int] | None = None, event: str | None = None):
    return service.delete_entries(db, int(org.id), ids, event)


@tool(
    "points.imports",
    description=(
        "The org's newest attendance CSV imports: status, rows done of rows total, points awarded, "
        "duplicates skipped, and the CSV row, email and message of each failed row."
    ),
    scope="members:read",
    module="points",
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}},
        "additionalProperties": False,
    },
)
def points_imports(db, org, caller, limit: int = 10):
    return {"imports": csv_import.runs(db, int(org.id), limit)}
