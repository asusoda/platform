"""Points tools."""

from core.tools import tool
from modules.points import service

MEMBER = {"type": "string", "minLength": 1, "maxLength": 255, "description": "Email, uuid, username or Discord id"}
EVENT = {"type": "string", "minLength": 1, "maxLength": 255}
ENTRY_IDS = {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": service.MAX_IDS}
MAX_CSV = 2_000_000


@tool(
    "points.leaderboard",
    description="Top members by points in this organization. Names and totals only.",
    scope="points:read",
    module="points",
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10}},
        "additionalProperties": False,
    },
)
def points_leaderboard(db, org, caller, limit: int = 10):
    return {"leaderboard": service.leaderboard(db, org, limit)}


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
    confirm=True,
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
    "points.import_csv",
    description=(
        "Give event_points to each checked-in row of an attendance CSV, once per email, in the background. "
        "A row with no member makes one."
    ),
    scope="points:write",
    module="points",
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
    from core.jobs import defer

    defer(
        "points.import_event_csv",
        file_content=content,
        event_name=event_name,
        event_points=event_points,
        org_prefix=str(org.prefix),
    )
    return {"queued": True}
