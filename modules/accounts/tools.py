"""Canvas tools for agents: one member's courses, assignments, grades, announcements and calendar. No Flask here.

Each tool reads Canvas with the Canvas grant of the member named by discord_id, in the caller's org, and no
other grant. The tools show only when the deployment has the Canvas provider on. They are read-only. Their
results go back to the caller only and are never added to knowledge or written to the logs.
"""

from core.tools import tool
from modules.accounts import canvas
from modules.auth import scopes

scopes.declare("canvas:read", "Read a member's own Canvas courses, assignments, grades, announcements and calendar")

PRIVATE = (
    " Uses only the Canvas account that this member connected. The result is private to that member: show it "
    "only to that member, for example in a direct message, and never in a channel or to another person. "
    "If the member has not connected Canvas, the error says how to start the login."
)

MEMBER = {
    "type": "object",
    "properties": {"discord_id": {"type": "string", "pattern": "^[0-9]{1,32}$", "description": "The member"}},
    "required": ["discord_id"],
    "additionalProperties": False,
}


@tool(
    "canvas.courses",
    description="List the Canvas courses the member is enrolled in this term." + PRIVATE,
    scope="canvas:read",
    input_schema=MEMBER,
    available=canvas.available,
)
def canvas_courses(db, org, caller, discord_id: str):
    return canvas.read(db, int(org.id), discord_id, canvas.courses)


@tool(
    "canvas.assignments",
    description="List the member's upcoming Canvas assignments to submit, with due dates, soonest first." + PRIVATE,
    scope="canvas:read",
    input_schema=MEMBER,
    available=canvas.available,
)
def canvas_assignments(db, org, caller, discord_id: str):
    return canvas.read(db, int(org.id), discord_id, canvas.assignments)


@tool(
    "canvas.grades",
    description="List the member's current grade in each active Canvas course." + PRIVATE,
    scope="canvas:read",
    input_schema=MEMBER,
    available=canvas.available,
)
def canvas_grades(db, org, caller, discord_id: str):
    return canvas.read(db, int(org.id), discord_id, canvas.grades)


@tool(
    "canvas.announcements",
    description="List recent announcements across the member's active Canvas courses." + PRIVATE,
    scope="canvas:read",
    input_schema=MEMBER,
    available=canvas.available,
)
def canvas_announcements(db, org, caller, discord_id: str):
    return canvas.read(db, int(org.id), discord_id, canvas.announcements)


@tool(
    "canvas.calendar",
    description="List the member's upcoming Canvas calendar events, soonest first." + PRIVATE,
    scope="canvas:read",
    input_schema=MEMBER,
    available=canvas.available,
)
def canvas_calendar(db, org, caller, discord_id: str):
    return canvas.read(db, int(org.id), discord_id, canvas.calendar)


@tool(
    "canvas.assignment_grades",
    description="List the member's score on each graded Canvas assignment, by course." + PRIVATE,
    scope="canvas:read",
    input_schema=MEMBER,
    available=canvas.available,
)
def canvas_assignment_grades(db, org, caller, discord_id: str):
    return canvas.read(db, int(org.id), discord_id, canvas.assignment_grades)
