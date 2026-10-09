"""Uptime tools."""

from core.tools import tool

from . import service


@tool(
    "uptime.list",
    description=(
        "The org's uptime monitors: target, state (up, down or null before the first check), "
        "percent up over 24 hours and 7 days, and the last check with its status code, latency and error."
    ),
    scope="uptime:read",
    module="uptime",
)
def uptime_list(db, org, caller):
    monitors = service.list_monitors(db, int(org.id))
    return {"monitors": [{k: v for k, v in m.items() if k != "recent"} for m in monitors]}
