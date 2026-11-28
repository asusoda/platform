"""The error log for officers: the org's errors, resolve and reopen, dashboard reports, and alerts.

core/error_log.py stores the errors. setup() installs its handler in a process and adds the org lookup and
the alert. A new error group, or a resolved one that comes back, sends the errors event (core/webhooks.py) to the
org's destinations, and to ERROR_WEBHOOK_URL from .env when it is set (modules/alerts/delivery.py). No Flask here.
"""

import os
from typing import cast

from sqlalchemy import or_

from core import error_log, webhooks
from core.db import session
from core.errors import ServiceError
from modules.alerts.models import Destination
from modules.organizations.models import Organization

MAX_REPORT_FIELD = 5000

webhooks.declare(
    "errors",
    "Errors",
    "A new error, or a resolved error that comes back. At most 30 messages an hour.",
)


class ErrorLogError(ServiceError, ValueError):
    pass


def _org_prefix(value: str | None) -> str | None:
    """The org prefix for a prefix, an org id or a guild id from a request, else the value."""
    if not value or not value.isdigit():
        return value
    with session() as db:
        org = db.query(Organization).filter(or_(Organization.id == int(value), Organization.guild_id == value)).first()
        return str(org.prefix) if org is not None else value


def _message(group: dict) -> webhooks.Message:
    where = " · ".join(p for p in (group["source"], group.get("org"), group.get("route") or group.get("location")) if p)
    return webhooks.Message(
        title=str(group["kind"]), text=str(group["message"]), color=webhooks.RED, footer=where or None
    )


def _alert(group: dict) -> None:
    """Queue a new or returning error group for the org's destinations and ERROR_WEBHOOK_URL."""
    webhooks.emit(group.get("org"), "errors", _message(group), server=bool(os.environ.get("ERROR_WEBHOOK_URL")))


def setup(source: str) -> None:
    """Record this process's errors as source (api, bot, worker, mcp), with org lookup and Discord alerts."""
    error_log.set_org_resolver(_org_prefix)
    error_log.on_new_group(_alert)
    error_log.install(source)


def listing(db, org: Organization, status: str = "open", limit: int = 50) -> dict:
    """The org's error groups, newest first, and the number open."""
    prefix = str(org.prefix)
    if status not in ("open", "resolved", "all"):
        raise ErrorLogError("status must be open, resolved or all")
    return {
        "errors": error_log.list_groups(db, org=prefix, status=status, limit=limit),
        **error_log.counts(db, org=prefix),
        "webhook_set": _sends_errors(db, org.id),
    }


def _sends_errors(db, org_id: int) -> bool:
    """True when an enabled webhook of the org takes the errors event."""
    rows = db.query(Destination).filter_by(organization_id=org_id, enabled=True).all()
    return any("errors" in (row.events or []) for row in rows)


def _ids(value: object) -> list[int]:
    if not isinstance(value, list) or not value or len(value) > 200 or not all(isinstance(i, int) for i in value):
        raise ErrorLogError("ids must be a list of 1 to 200 error ids")
    return cast(list[int], value)


def resolve(db, org: Organization, ids: object, actor: str | None) -> dict:
    return {"changed": error_log.set_resolved(db, _ids(ids), resolved=True, actor=actor, org=str(org.prefix))}


def reopen(db, org: Organization, ids: object) -> dict:
    return {"changed": error_log.set_resolved(db, _ids(ids), resolved=False, actor=None, org=str(org.prefix))}


def delete(db, org: Organization, ids: object) -> dict:
    """Delete error groups of the org. A deleted error that happens again starts a new group."""
    return {"deleted": error_log.delete_groups(db, _ids(ids), org=str(org.prefix))}


def report(org: Organization, body: object) -> dict:
    """Record an error from the dashboard in the browser."""
    if not isinstance(body, dict):
        raise ErrorLogError("Send a JSON object with kind and message")
    data = cast(dict[str, object], body)
    fields = {k: data.get(k) for k in ("kind", "message", "stack", "page")}
    if not isinstance(fields["kind"], str) or not isinstance(fields["message"], str) or not fields["message"]:
        raise ErrorLogError("kind and message must be text")
    if any(v is not None and not isinstance(v, str) for v in fields.values()):
        raise ErrorLogError("kind, message, stack and page must be text")
    page = cast(str | None, fields["page"])
    error_log.capture(
        source="browser",
        kind=fields["kind"][:200] or "Error",
        message=cast(str, fields["message"])[:MAX_REPORT_FIELD],
        stack=cast(str | None, fields["stack"]),
        location=page[:255] if page else None,
        org=str(org.prefix),
        route=page[:255] if page else None,
        group_key=cast(str, fields["message"])[:200],
    )
    return {"recorded": True}
