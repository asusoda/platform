"""Alert feed tools."""

from core.tools import tool

from . import service

KEY = {"type": "string", "minLength": 1, "maxLength": 40}
ONLY_KEY = {"type": "object", "properties": {"key": KEY}, "required": ["key"], "additionalProperties": False}


@tool(
    "alerts.list",
    description="The org's alert feeds, their schedule and last run.",
    scope="alerts:manage",
    module="alerts",
)
def alerts_list(db, org, caller):
    return {"feeds": service.list_feeds(db, int(org.id))}


@tool(
    "alerts.presets",
    description="Feeds that packs offer, with the kind and config to pass to alerts.save.",
    scope="alerts:manage",
    module="alerts",
)
def alerts_presets(db, org, caller):
    return {"presets": service.presets(db, int(org.id))}


@tool(
    "alerts.history",
    description="A feed's recent runs and the items it posted.",
    scope="alerts:manage",
    module="alerts",
    input_schema=ONLY_KEY,
)
def alerts_history(db, org, caller, key: str):
    return service.history(db, int(org.id), key)


@tool(
    "alerts.save",
    description=(
        "Create or change an alert feed. kind is github_jobs or hackathons. A new feed needs webhook_url, "
        "a Discord webhook URL; it is stored encrypted and never returned."
    ),
    scope="alerts:manage",
    module="alerts",
    input_schema={
        "type": "object",
        "properties": {
            "key": KEY,
            "kind": {"type": "string", "enum": sorted(service.KINDS)},
            "config": {"type": "object"},
            "every_hours": {"type": "integer", "minimum": 1, "maximum": 168},
            "enabled": {"type": "boolean"},
            "webhook_url": {"type": "string", "maxLength": 300},
        },
        "required": ["key"],
        "additionalProperties": False,
    },
)
def alerts_save(db, org, caller, key: str, **body):
    feed, created = service.put_feed(db, int(org.id), key, body, caller.actor)
    return {"feed": feed, "created": created}


@tool(
    "alerts.delete",
    description="Delete an alert feed, its history and its webhook.",
    scope="alerts:manage",
    module="alerts",
    confirm=True,
    input_schema=ONLY_KEY,
)
def alerts_delete(db, org, caller, key: str):
    service.delete_feed(db, int(org.id), key)
    return {"deleted": key}


@tool(
    "alerts.run",
    description="Run a feed now and post its new items. post_existing also posts items seen before the first run.",
    scope="alerts:manage",
    module="alerts",
    input_schema={
        "type": "object",
        "properties": {"key": KEY, "post_existing": {"type": "boolean"}},
        "required": ["key"],
        "additionalProperties": False,
    },
)
def alerts_run(db, org, caller, key: str, post_existing: bool = False):
    return service.run_now(db, int(org.id), key, post_existing=post_existing)
