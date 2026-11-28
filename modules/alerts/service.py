"""Alerts: the org's destinations (outbound webhooks), the events each one gets, and the log of sent messages.

core/webhooks.py has the events. delivery.py sends every message and logs it in deliveries. A URL must match its
kind and name a public host. It is encrypted with SECRETS_KEY and no route returns it. Feeds post to a
destination too; the listing names them, so officers see every place that Platform sends to. No Flask here.
"""

from datetime import datetime
from typing import cast

from core import limits, net, secrets, webhooks
from core.errors import ServiceError
from modules.feeds import service as feeds
from modules.feeds.models import AlertFeed
from modules.organizations import service as organizations
from modules.organizations.models import Organization

from . import delivery
from .models import Delivery, Destination

WEBHOOKS_LIMIT = "alerts.destinations"
limits.declare(
    WEBHOOKS_LIMIT,
    "alerts",
    "Alert destinations",
    20,
    unit="destinations",
    usage=lambda db, org_id: db.query(Destination).filter_by(organization_id=org_id).count(),
)
MAX_IDS = 100  # ids in one bulk call
MAX_NAME = 100
MAX_DELIVERIES = 100  # rows in one page of the log
SOURCES = ("event", "feed", "leetcode", "test")
STATUSES = ("sent", "failed")


class WebhookError(ServiceError, ValueError):
    pass


def _iso(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _dict(row: Destination) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "url_hint": row.url_hint,
        "events": list(cast(list[str], row.events) or []),
        "enabled": bool(row.enabled),
        "last_sent_at": _iso(row.last_sent_at),
        "last_error": row.last_error,
        "created_at": _iso(row.created_at),
        "created_by": row.created_by,
    }


def events(org: Organization) -> list[dict]:
    """The events an officer can pick: each event whose module is on for the org."""
    return [
        {"key": e.key, "label": e.label, "description": e.description, "module": e.module}
        for e in webhooks.EVENTS.values()
        if e.module is None or organizations.module_enabled(org, e.module)
    ]


def _feeds(db, org: Organization) -> list[dict]:
    return [
        {
            "key": f["key"],
            "kind": f["kind"],
            "enabled": f["enabled"],
            "destination_id": f["destination_id"],
            "webhook_set": f["webhook_set"],
            "last_run_at": f["last_run_at"],
            "last_error": f["last_error"],
        }
        for f in feeds.list_feeds(db, org.id)
    ]


def listing(db, org: Organization) -> dict:
    """The org's destinations, the events and kinds to pick from, and the org's feeds."""
    rows = db.query(Destination).filter_by(organization_id=org.id).order_by(Destination.name).all()
    return {
        "webhooks": [_dict(row) for row in rows],
        "events": events(org),
        "kinds": [{"key": k.key, "label": k.label, "example": k.example} for k in delivery.KINDS.values()],
        "feeds": _feeds(db, org),
        "secrets_key": secrets.configured(),
    }


def _find(db, org: Organization, webhook_id: int) -> Destination:
    row = db.query(Destination).filter_by(organization_id=org.id, id=webhook_id).first()
    if row is None:
        raise WebhookError("No webhook with that id", 404)
    return row


def _name(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > MAX_NAME:
        raise WebhookError(f"name must be text of 1 to {MAX_NAME} characters")
    return value.strip()


def _events(org: Organization, value: object, saved: object = ()) -> list[str]:
    """The chosen event keys, which may be none. Saved keys of a module that is off stay, as the officer cannot see
    them."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise WebhookError("events must be a list of event keys")
    known = [e["key"] for e in events(org)]
    hidden = [key for key in cast(list[str], saved or []) if key not in known]
    unknown = sorted(set(cast(list[str], value)) - set(known) - set(hidden))
    if unknown:
        raise WebhookError(f"Unknown events: {', '.join(unknown)}")
    return [key for key in known if key in value] + hidden


def _url(kind: str, value: object) -> tuple[str, str]:
    """The encrypted URL and its hint. Raises when the URL does not match the kind or is not public."""
    destination = delivery.KINDS[kind]
    if not isinstance(value, str) or not destination.pattern.match(value.strip()):
        raise WebhookError(f"Use a {destination.label} webhook URL: {destination.example}")
    url = value.strip()
    try:
        net.check_public(url)
    except ValueError as e:
        raise WebhookError(str(e)) from e
    ciphertext = secrets.encrypt(url)
    if ciphertext is None:
        raise WebhookError("SECRETS_KEY is not configured on this server")
    return ciphertext, destination.hint(url)


def _unique(db, org: Organization, name: str, webhook_id: int | None = None) -> None:
    other = db.query(Destination).filter_by(organization_id=org.id, name=name).first()
    if other is not None and other.id != webhook_id:
        raise WebhookError("Another webhook has that name", 409)


def create(db, org: Organization, body: dict, actor: str | None) -> dict:
    """Add a webhook. Commits."""
    kind = body.get("kind", "discord")
    if kind not in delivery.KINDS:
        raise WebhookError(f"kind must be one of {', '.join(delivery.KINDS)}")
    name = _name(body.get("name"))
    chosen = _events(org, body.get("events", []))
    _unique(db, org, name)
    limits.check(db, org.id, WEBHOOKS_LIMIT)
    ciphertext, hint = _url(kind, body.get("url"))
    row = Destination(
        organization_id=org.id,
        name=name,
        kind=kind,
        url_ciphertext=ciphertext,
        url_hint=hint,
        events=chosen,
        enabled=body.get("enabled", True) is not False,
        created_by=actor,
    )
    db.add(row)
    db.commit()
    return _dict(row)


def update(db, org: Organization, webhook_id: int, body: dict) -> dict:
    """Change the name, URL, events or switch of a webhook. A missing key keeps its value. Commits."""
    row = _find(db, org, webhook_id)
    if "name" in body:
        name = _name(body["name"])
        _unique(db, org, name, webhook_id)
        row.name = name
    if "events" in body:
        row.events = _events(org, body["events"], row.events)
    if "enabled" in body:
        if not isinstance(body["enabled"], bool):
            raise WebhookError("enabled must be true or false")
        row.enabled = body["enabled"]
    if body.get("url") is not None:
        row.url_ciphertext, row.url_hint = _url(str(row.kind), body["url"])
        row.last_error = None
    db.commit()
    return _dict(row)


def delete(db, org: Organization, webhook_id: int) -> None:
    """Delete a destination. Refuses while a feed posts to it. Commits."""
    row = _find(db, org, webhook_id)
    used = [key for (key,) in db.query(AlertFeed.key).filter_by(organization_id=org.id, destination_id=webhook_id)]
    if used:
        raise WebhookError(f"Feeds post here: {', '.join(sorted(used))}. Give them another destination first", 409)
    db.delete(row)
    db.commit()


def send_test(db, org: Organization, webhook_id: int) -> dict:
    """Post a test message to the destination now and save the result. Commits."""
    row = _find(db, org, webhook_id)
    target = delivery.target_of(row)
    if target is None:
        return {"ok": False, "message": "The URL cannot be read with SECRETS_KEY. Save the URL again."}
    labels = {e.key: e.label for e in webhooks.EVENTS.values()}
    chosen = ", ".join(labels.get(k, k) for k in row.events or [])
    message = webhooks.Message(
        title=f"Test from {org.name}",
        text=f"This webhook works. It sends: {chosen}." if chosen else "This webhook works. It gets no events.",
        color=webhooks.GREEN,
    )
    error = delivery.deliver(db, target, message, "test", "test")
    return {"ok": error is None, "message": error or "Sent. Look for the message in the channel."}


def _delivery(row: Delivery, guild_id: str | None) -> dict:
    link = None
    if guild_id and row.channel_id and row.message_id:
        link = f"https://discord.com/channels/{guild_id}/{row.channel_id}/{row.message_id}"
    return {
        "id": row.id,
        "destination_id": row.destination_id,
        "source": row.source,
        "ref": row.ref,
        "title": row.title,
        "status": row.status,
        "error": row.error,
        "message_url": link,
        "created_at": _iso(row.created_at),
    }


def _choice(name: str, value: object, allowed: tuple[str, ...]) -> str | None:
    if value in (None, ""):
        return None
    if value not in allowed:
        raise WebhookError(f"{name} must be one of {', '.join(allowed)}")
    return cast(str, value)


def _number(name: str, value: object, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    try:
        number = int(cast(str, value))
    except (TypeError, ValueError) as e:
        raise WebhookError(f"{name} must be a whole number") from e
    if number < 1:
        raise WebhookError(f"{name} must be 1 or more")
    return number


def deliveries(
    db,
    org: Organization,
    source: object = None,
    destination_id: object = None,
    status: object = None,
    before: object = None,
    limit: object = None,
) -> dict:
    """The org's sent and failed messages, newest first. before is the id to page from; next is the next one."""
    size = min(cast(int, _number("limit", limit, 50)), MAX_DELIVERIES)
    query = db.query(Delivery).filter(Delivery.organization_id == org.id)
    if (chosen := _choice("source", source, SOURCES)) is not None:
        query = query.filter(Delivery.source == chosen)
    if (chosen := _choice("status", status, STATUSES)) is not None:
        query = query.filter(Delivery.status == chosen)
    if (number := _number("destination_id", destination_id)) is not None:
        query = query.filter(Delivery.destination_id == number)
    if (number := _number("before", before)) is not None:
        query = query.filter(Delivery.id < number)
    rows = query.order_by(Delivery.id.desc()).limit(size + 1).all()
    guild_id = str(org.guild_id) if org.guild_id else None
    page = rows[:size]
    return {
        "deliveries": [_delivery(row, guild_id) for row in page],
        "next": page[-1].id if len(rows) > size else None,
    }
