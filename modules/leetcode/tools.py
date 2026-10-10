"""LeetCode daily post tools."""

from core.tools import ToolError, tool
from modules.leetcode import service

SNOWFLAKE = {"type": ["string", "null"], "pattern": service.SNOWFLAKE.pattern}


@tool(
    "leetcode.settings",
    description="The org's daily LeetCode post: channel_id, role_ping and daily_time (HH:MM).",
    scope="org:read",
    module="leetcode",
)
def leetcode_settings(db, org, caller):
    return {"settings": service.settings(org)}


@tool(
    "leetcode.update_settings",
    description="Change the daily LeetCode post. null clears a value; a missing key is kept.",
    scope="settings:write",
    module="leetcode",
    input_schema={
        "type": "object",
        "properties": {
            "channel_id": SNOWFLAKE,
            "role_ping": SNOWFLAKE,
            "daily_time": {"type": ["string", "null"], "pattern": service.HHMM.pattern},
        },
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def leetcode_update_settings(db, org, caller, **changes):
    try:
        return {"settings": service.save_settings(db, org, changes)}
    except service.SettingsError as e:
        raise ToolError(str(e), 400) from e
