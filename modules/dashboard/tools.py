"""Dashboard tools: the overview, trends, notifications, errors, audit log, integrations, webhooks and CI runs."""

from core import audit
from core.integrations import registry as integrations
from core.tools import ToolError, tool
from core.webhooks import Webhook
from modules.auth import scopes
from modules.integrations import oauth

from . import ci, errors, notices, service, trends, webhooks

scopes.declare(
    "webhooks:manage", "List, add, change, test and delete the org's outbound webhooks. URLs are never returned"
)

IDS = {"type": "array", "items": {"type": "string", "maxLength": 200}, "minItems": 1, "maxItems": 200}
ERROR_IDS = {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 200}
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
    "notifications.delete",
    description="Delete events from the notification list by id. A problem cannot be deleted; resolve it instead.",
    scope="settings:write",
    confirm=True,
    input_schema={"type": "object", "properties": {"ids": IDS}, "required": ["ids"], "additionalProperties": False},
)
def notifications_delete(db, org, caller, ids: list[str]):
    return notices.delete(db, org, ids)


@tool(
    "errors.list",
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
    "errors.resolve",
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
    "errors.reopen",
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
    "errors.delete",
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


@tool(
    "integrations.disconnect",
    description="Sign out of an integration that an officer connected with a sign-in, such as Notion or Google.",
    scope="integrations:manage",
    confirm=True,
    input_schema={"type": "object", "properties": {"key": KEY}, "required": ["key"], "additionalProperties": False},
)
def integrations_disconnect(db, org, caller, key: str):
    oauth.disconnect(db, int(org.id), key)
    return {"disconnected": key}


@tool(
    "ci.runs",
    description="The latest GitHub Actions runs of each repository on the org's CI list.",
    scope="activity:read",
)
def ci_runs(db, org, caller):
    return ci.runs(db, org)


@tool(
    "ci.set_repos",
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


WEBHOOK_ID = {"type": "integer", "minimum": 1}


@tool(
    "webhooks.list",
    description="The org's webhooks, the events and kinds to pick from, and the alert feeds. URLs are never returned.",
    scope="webhooks:manage",
)
def webhooks_list(db, org, caller):
    return webhooks.listing(db, org)


@tool(
    "webhooks.save",
    description=(
        "Add a webhook, or change the webhook with id. A new webhook needs name, events and url. The URL must "
        "match the kind and is stored encrypted. A missing field is kept."
    ),
    scope="webhooks:manage",
    input_schema={
        "type": "object",
        "properties": {
            "id": WEBHOOK_ID,
            "name": {"type": "string", "minLength": 1, "maxLength": webhooks.MAX_NAME},
            "kind": {"type": "string", "maxLength": 32},
            "url": {"type": "string", "maxLength": 1000},
            "events": {"type": "array", "items": {"type": "string", "maxLength": 64}, "minItems": 1},
            "enabled": {"type": "boolean"},
        },
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def webhooks_save(db, org, caller, id: int | None = None, **body):
    if id is None:
        return {"webhook": webhooks.create(db, org, body, caller.actor)}
    return {"webhook": webhooks.update(db, org, id, body)}


@tool(
    "webhooks.test",
    description="Send a test message to a webhook now and return whether it worked.",
    scope="webhooks:manage",
    input_schema={
        "type": "object",
        "properties": {"id": WEBHOOK_ID},
        "required": ["id"],
        "additionalProperties": False,
    },
)
def webhooks_test(db, org, caller, id: int):
    return webhooks.send_test(db, org, id)


@tool(
    "webhooks.delete",
    description="Delete webhooks by id, up to 20. If one id is missing, nothing changes.",
    scope="webhooks:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"ids": {"type": "array", "items": WEBHOOK_ID, "minItems": 1, "maxItems": webhooks.MAX_WEBHOOKS}},
        "required": ["ids"],
        "additionalProperties": False,
    },
)
def webhooks_delete(db, org, caller, ids: list[int]):
    known = {row.id for row in db.query(Webhook.id).filter(Webhook.organization_id == org.id, Webhook.id.in_(ids))}
    missing = sorted(set(ids) - known)
    if missing:
        raise ToolError(f"No webhooks with ids {', '.join(str(i) for i in missing)}", 404)
    for webhook_id in sorted(known):
        webhooks.delete(db, org, webhook_id)
    return {"deleted": sorted(known)}
