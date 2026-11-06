"""Dashboard tools: the overview, trends, notifications, errors, audit log, integrations and CI runs."""

from core import audit
from core.integrations import registry as integrations
from core.tools import tool
from modules.integrations import oauth

from . import ci, errors, notices, service, trends

IDS = {"type": "array", "items": {"type": "string", "maxLength": 200}, "minItems": 1, "maxItems": 200}
ERROR_IDS = {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 200}
KEY = {"type": "string", "minLength": 1, "maxLength": 64}


@tool(
    "org.overview",
    description="The org at a glance: members, points, store, Godfather, webhook feeds, apps, knowledge, agents and tokens.",
    scope="activity:read",
)
def org_overview(db, org, caller):
    return service.overview(db, org)


@tool(
    "org.trends",
    description="Daily counts for the last days days: actions, job runs, points, orders, questions, webhook posts.",
    scope="activity:read",
    input_schema={
        "type": "object",
        "properties": {"days": {"type": "integer", "minimum": 7, "maximum": trends.MAX_DAYS}},
        "additionalProperties": False,
    },
)
def org_trends(db, org, caller, days: int = trends.DEFAULT_DAYS):
    return trends.trends(db, org, days)


@tool("activity.notifications", description="Open and resolved problems the dashboard shows.", scope="activity:read")
def notifications_list(db, org, caller):
    return notices.listing(db, org)


@tool(
    "activity.resolve_notification",
    description="Mark notifications resolved by id. One shows again when its error message changes.",
    scope="settings:write",
    input_schema={"type": "object", "properties": {"ids": IDS}, "required": ["ids"], "additionalProperties": False},
)
def notifications_resolve(db, org, caller, ids: list[str]):
    return notices.resolve(db, org, ids, caller.actor)


@tool(
    "activity.reopen_notification",
    description="Open resolved notifications again by id.",
    scope="settings:write",
    input_schema={"type": "object", "properties": {"ids": IDS}, "required": ["ids"], "additionalProperties": False},
)
def notifications_reopen(db, org, caller, ids: list[str]):
    return notices.reopen(db, org, ids)


@tool(
    "activity.delete_notification",
    description="Delete events from the notification list by id. A problem cannot be deleted; resolve it instead.",
    scope="settings:write",
    confirm=True,
    input_schema={"type": "object", "properties": {"ids": IDS}, "required": ["ids"], "additionalProperties": False},
)
def notifications_delete(db, org, caller, ids: list[str]):
    return notices.delete(db, org, ids)


@tool(
    "activity.errors",
    description="Errors recorded by Platform for the org, newest first: type, message, where, count and stack.",
    scope="activity:read",
    input_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["open", "resolved", "all"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        "additionalProperties": False,
    },
)
def errors_list(db, org, caller, status: str = "open", limit: int = 50):
    return errors.listing(db, org, status, limit)


@tool(
    "activity.resolve_error",
    description="Mark errors resolved by id. An error shows again when it happens again.",
    scope="settings:write",
    input_schema={
        "type": "object",
        "properties": {"ids": ERROR_IDS},
        "required": ["ids"],
        "additionalProperties": False,
    },
)
def errors_resolve(db, org, caller, ids: list[int]):
    return errors.resolve(db, org, ids, caller.actor)


@tool(
    "activity.reopen_error",
    description="Open resolved errors again by id.",
    scope="settings:write",
    input_schema={
        "type": "object",
        "properties": {"ids": ERROR_IDS},
        "required": ["ids"],
        "additionalProperties": False,
    },
)
def errors_reopen(db, org, caller, ids: list[int]):
    return errors.reopen(db, org, ids)


@tool(
    "activity.delete_error",
    description="Delete errors by id. An error that happens again after a delete starts a new entry.",
    scope="settings:write",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"ids": ERROR_IDS},
        "required": ["ids"],
        "additionalProperties": False,
    },
)
def errors_delete(db, org, caller, ids: list[int]):
    return errors.delete(db, org, ids)


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
    "connections.list",
    description="Each integration, its fields, and whether the org set them. Secret values are never returned.",
    scope="integrations:manage",
)
def integrations_list(db, org, caller):
    return {"integrations": integrations.status(db, int(org.id))}


@tool(
    "connections.save",
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
    "connections.test",
    description="Check an integration's keys with one call to its service.",
    scope="integrations:manage",
    input_schema={"type": "object", "properties": {"key": KEY}, "required": ["key"], "additionalProperties": False},
)
def integrations_test(db, org, caller, key: str):
    try:
        return {"ok": True, "message": integrations.test(db, int(org.id), key)}
    except integrations.IntegrationError as e:
        return {"ok": False, "message": e.message}


@tool(
    "connections.disconnect",
    description="Sign out of an integration that an officer connected with a sign-in, such as Notion or Google.",
    scope="integrations:manage",
    confirm=True,
    input_schema={"type": "object", "properties": {"key": KEY}, "required": ["key"], "additionalProperties": False},
)
def integrations_disconnect(db, org, caller, key: str):
    oauth.disconnect(db, int(org.id), key)
    return {"disconnected": key}


@tool(
    "activity.ci_runs",
    description="The latest GitHub Actions runs of each repository on the org's CI list.",
    scope="activity:read",
)
def ci_runs(db, org, caller):
    return ci.runs(db, org)


@tool(
    "activity.set_ci_repos",
    description="Replace the org's CI repository list with owner/name repositories.",
    scope="settings:write",
    input_schema={
        "type": "object",
        "properties": {
            "repos": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": ci.MAX_REPOS}
        },
        "required": ["repos"],
        "additionalProperties": False,
    },
)
def ci_set_repos(db, org, caller, repos: list[str]):
    return {"repos": ci.set_repos(db, org, repos)}
