"""Leaderboard tools."""

from core.tools import tool
from modules.points.submodules.leaderboard import service


@tool(
    "points.leaderboard",
    description="Top members by points in this organization. Names and totals only.",
    scope="points:read",
    module="points.leaderboard",
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10}},
        "additionalProperties": False,
    },
)
def points_leaderboard(db, org, caller, limit: int = 10):
    return {"leaderboard": service.leaderboard(db, org, limit)}
