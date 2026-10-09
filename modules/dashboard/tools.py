"""Dashboard tools: the overview, trends, notifications, audit log and integrations."""

from core import audit
from core.integrations import registry as integrations
from core.tools import tool

from . import notices, service, trends

IDS = {"type": "array", "items": {"type": "string", "maxLength": 200}, "minItems": 1, "maxItems": 200}
KEY = {"type": "string", "minLength": 1, "maxLength": 64}


@tool(
    "org.overview",
    description="The org at a glance: members, points, store, compute, alerts, apps, knowledge, agents and tokens.",
    scope="activity:read",
)
def org_overview(db, org, caller):
    return service.overview(db, org)


@tool(
    "org.trends",
    description="Daily counts for the last days days: actions, job runs, points, orders, questions, alerts posted.",
    scope="activity:read",
    input_schema={
        "type": "object",
        "properties": {"days": {"type": "integer", "minimum": 7, "maximum": trends.MAX_DAYS}},
        "additionalProperties": False,
    },
)
def org_trends(db, org, caller, days: int = trends.DEFAULT_DAYS):
    return trends.trends(db, org, days)


@tool("notifications.list", description="Open and resolved problems the dashboard shows.", scope="activity:read")
def notifications_list(db, org, caller):
    return notices.listing(db, org)


@tool(
    "notifications.resolve",
    description="Mark notifications resolved by id. One shows again when its error message changes.",
    scope="settings:write",
    input_schema={"type": "object", "properties": {"ids": IDS}, "required": ["ids"], "additionalProperties": False},
)
def notifications_resolve(db, org, caller, ids: list[str]):
    return notices.resolve(db, org, ids, caller.actor)


@tool(
    "notifications.reopen",
    description="Open resolved notifications again by id.",
    scope="settings:write",
    input_schema={"type": "object", "properties": {"ids": IDS}, "required": ["ids"], "additionalProperties": False},
)
def notifications_reopen(db, org, caller, ids: list[str]):
    return notices.reopen(db, org, ids)


@tool(
    "activity.log",
    description="The org's audit log, newest first: who did what, from where, and the status.",
    scope="activity:read",
    input_schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            "before_id": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
)
def activity_log(db, org, caller, limit: int = 50, before_id: int | None = None):
    return {"entries": audit.list_entries(db, org=str(org.prefix), limit=limit, before_id=before_id)}


@tool(
    "integrations.list",
    description="Each integration, its fields, and whether the org set them. Secret values are never returned.",
    scope="integrations:manage",
)
def integrations_list(db, org, caller):
    return {"integrations": integrations.status(db, int(org.id))}


@tool(
    "integrations.save",
    description="Set or clear an integration's fields. A null value clears that field; a missing field is kept.",
    scope="integrations:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {
            "key": KEY,
            "fields": {"type": "object", "additionalProperties": {"type": ["string", "null"], "maxLength": 20000}},
        },
        "required": ["key", "fields"],
        "additionalProperties": False,
    },
)
def integrations_save(db, org, caller, key: str, fields: dict):
    integrations.save(db, int(org.id), key, fields, caller.actor)
    return {"saved": key}


@tool(
    "integrations.test",
    description="Check an integration's keys with one call to its service.",
    scope="integrations:manage",
    input_schema={"type": "object", "properties": {"key": KEY}, "required": ["key"], "additionalProperties": False},
)
def integrations_test(db, org, caller, key: str):
    try:
        return {"ok": True, "message": integrations.test(db, int(org.id), key)}
    except integrations.IntegrationError as e:
        return {"ok": False, "message": e.message}
