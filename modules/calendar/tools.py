"""Calendar tools."""

from core.tools import ToolError, tool
from modules.calendar import service


@tool(
    "events.list",
    description="Upcoming events from the organization's calendar: title, start, end, location, description.",
    scope="calendar:read",
    module="calendar",
)
def events_list(db, org, caller):
    try:
        result = service.list_events(db, org)
    except service.CalendarError as e:
        raise ToolError(e.message, e.status) from e
    if isinstance(result, dict) and result.get("status") == "error":
        raise ToolError(str(result.get("message", "Calendar unavailable")), 502)
    return {"events": result.get("events", [])}
