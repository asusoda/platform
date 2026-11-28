"""The one send path: every message that Platform posts to a destination goes through deliver().

deliver() formats the message for the destination's kind, posts it to a public host with no redirects, waits
once when the service asks to slow down, saves the result on the destination, writes a deliveries row and logs
one line. A message that another sender posts, such as the bot's LeetCode daily post, is logged with log_post().
send_event() is the events.deliver handler (core/webhooks.py): it sends an event to each enabled destination of
the org that takes it, when the event's module is on and the org is under alerts.messages for the event.
No error text or log line holds a URL. No Flask here.
"""

import os
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import requests

from core import limits, net, secrets, webhooks
from core.db import session
from core.log import get_logger
from core.time import utcnow
from modules.organizations import service as organizations
from modules.organizations.models import Organization

from .models import Delivery, Destination

logger = get_logger("alerts.delivery")

TIMEOUT_SECONDS = 10
MAX_RETRY_SECONDS = 10.0
SERVER_PER_HOUR = 30
MESSAGES_LIMIT = "alerts.messages"
limits.declare(
    MESSAGES_LIMIT, "alerts", "Alert messages for each event", 30, window="hour", unit="messages", paid_by="org"
)

# Discord's embed limits
EMBED_TITLE = 256
EMBED_DESCRIPTION = 4096
EMBED_FIELDS = 25
FIELD_NAME = 256
FIELD_VALUE = 1024
EMBED_FOOTER = 2048
EMBED_TOTAL = 6000


@dataclass(frozen=True)
class Kind:
    key: str
    label: str
    pattern: re.Pattern
    example: str
    format: Callable[[webhooks.Message], dict]
    hint: Callable[[str], str]


@dataclass(frozen=True)
class Target:
    """Where one message goes. destination_id is None for a feed's older webhook secret or ERROR_WEBHOOK_URL."""

    kind: str
    url: str
    destination_id: int | None = None
    organization_id: int | None = None


def _embed_size(embed: dict) -> int:
    fields = sum(len(f["name"]) + len(f["value"]) for f in embed.get("fields", []))
    return (
        len(embed["title"]) + len(embed.get("description", "")) + fields + len(embed.get("footer", {}).get("text", ""))
    )


def _discord(message: webhooks.Message) -> dict:
    """The Discord body. Empty keys are left out and each part fits Discord's embed limits."""
    embed: dict = {"title": message.title[:EMBED_TITLE] or "-", "color": message.color}
    if message.text:
        embed["description"] = message.text[:EMBED_DESCRIPTION]
    fields = [
        {"name": (name or "-")[:FIELD_NAME], "value": (value or "-")[:FIELD_VALUE], "inline": len(value) < 40}
        for name, value in message.fields[:EMBED_FIELDS]
    ]
    if fields:
        embed["fields"] = fields
    if message.url:
        embed["url"] = message.url
    if message.footer:
        embed["footer"] = {"text": message.footer[:EMBED_FOOTER]}
    if message.timestamp:
        embed["timestamp"] = message.timestamp
    over = _embed_size(embed) - EMBED_TOTAL
    if over > 0 and "description" in embed:
        embed["description"] = embed["description"][: max(0, len(embed["description"]) - over)]
        if not embed["description"]:
            del embed["description"]
    while _embed_size(embed) > EMBED_TOTAL and embed.get("fields"):
        embed["fields"].pop()
    return {"embeds": [embed], "allowed_mentions": {"parse": []}}


def _discord_hint(url: str) -> str:
    """The host and the last 4 digits of the webhook id. The token is not in it."""
    match = re.match(r"^https://([\w.]+)/api/webhooks/(\d+)/", url)
    return f"{match.group(1)} ...{match.group(2)[-4:]}" if match else "discord.com"


KINDS: dict[str, Kind] = {
    "discord": Kind(
        key="discord",
        label="Discord",
        pattern=re.compile(r"^https://(?:discord|discordapp)\.com/api/webhooks/\d+/[\w-]+$"),
        example="https://discord.com/api/webhooks/...",
        format=_discord,
        hint=_discord_hint,
    ),
}


def target_of(row: Destination) -> Target | None:
    """The target of a destination, or None when its URL cannot be read with SECRETS_KEY."""
    url = secrets.decrypt(str(row.url_ciphertext))
    if url is None:
        return None
    return Target(str(row.kind), url, int(row.id), int(row.organization_id))


def _retry_after(response: requests.Response) -> float:
    try:
        seconds = float(response.json().get("retry_after", 1))
    except (ValueError, AttributeError, TypeError):
        seconds = 1.0
    return min(max(seconds, 0.0), MAX_RETRY_SECONDS)


def _reason(response: requests.Response) -> str:
    """The service's own short reason, such as Discord's "Invalid Form Body", or an empty string."""
    try:
        reason = response.json().get("message")
    except (ValueError, AttributeError):
        return ""
    return f": {str(reason)[:200]}" if reason else ""


def post(kind: str, url: str, message: webhooks.Message) -> str | None:
    """Send one message. None when the service took it, else an error with no URL in it."""
    destination = KINDS.get(kind)
    if destination is None:
        return f"Unknown destination kind {kind}"
    body = destination.format(message)
    try:
        for attempt in range(2):
            response = net.post(url, json=body, timeout=TIMEOUT_SECONDS, allow_redirects=False)
            if response.status_code == 429 and attempt == 0:
                time.sleep(_retry_after(response))
                continue
            break
    except net.NotPublic:
        return f"The {destination.label} host is not a public address"
    except (requests.RequestException, ValueError) as e:
        return f"Could not reach {destination.label}: {type(e).__name__}"
    if response.status_code == 429:
        return f"{destination.label} rate limited the message twice (status 429)"
    if not 200 <= response.status_code < 300:
        return f"{destination.label} refused the message with status {response.status_code}{_reason(response)}"
    return None


def _log(org_id: int | None, destination_id: int | None, source: str, ref: str, error: str | None) -> None:
    if error:
        logger.warning(
            "alert delivery failed org=%s destination=%s source=%s ref=%s error=%s",
            org_id,
            destination_id,
            source,
            ref,
            error,
        )
    else:
        logger.info("alert sent org=%s destination=%s source=%s ref=%s", org_id, destination_id, source, ref)


def _row(org_id: int, destination_id: int | None, source: str, ref: str, title: str, error: str | None) -> Delivery:
    return Delivery(
        organization_id=org_id,
        destination_id=destination_id,
        source=source,
        ref=ref[:100],
        title=title[:256] or "-",
        status="failed" if error else "sent",
        error=error[:500] if error else None,
    )


def deliver(db, target: Target, message: webhooks.Message, source: str, ref: str) -> str | None:
    """Post the message, save the result on the destination and in deliveries, and log it. Commits.

    Returns the error, or None when the message was sent. A target with no org (ERROR_WEBHOOK_URL) gets no row.
    """
    error = post(target.kind, target.url, message)
    _record(db, target, source, ref, message.title, error)
    return error


def _record(db, target: Target, source: str, ref: str, title: str, error: str | None) -> None:
    if target.destination_id is not None:
        row = db.get(Destination, target.destination_id)
        if row is not None:
            row.last_sent_at = utcnow()
            row.last_error = error[:500] if error else None
    if target.organization_id is not None:
        db.add(_row(target.organization_id, target.destination_id, source, ref, title, error))
    db.commit()
    _log(target.organization_id, target.destination_id, source, ref, error)


def log_post(
    db,
    org_id: int,
    source: str,
    ref: str,
    title: str,
    channel_id: str | None = None,
    message_id: str | None = None,
    error: str | None = None,
) -> None:
    """Log a message that another sender posted, such as the bot. Commits."""
    row = _row(org_id, None, source, ref, title, error)
    row.channel_id, row.message_id = channel_id, message_id
    db.add(row)
    db.commit()
    _log(org_id, None, source, ref, error)


_server_sent: list[float] = []
_server_lock = threading.Lock()


def _server_allowed() -> bool:
    """At most SERVER_PER_HOUR messages an hour to ERROR_WEBHOOK_URL. Kept in memory: only the worker sends them."""
    now = time.monotonic()
    with _server_lock:
        _server_sent[:] = [t for t in _server_sent if now - t < 3600]
        if len(_server_sent) >= SERVER_PER_HOUR:
            return False
        _server_sent.append(now)
        return True


def _send_server(event: str, message: webhooks.Message) -> None:
    url = os.environ.get("ERROR_WEBHOOK_URL")
    if not url:
        return
    if not _server_allowed():
        logger.info("ERROR_WEBHOOK_URL over its hourly limit event=%s", event)
        return
    error = post("discord", url, message)
    _log(None, None, "server", event, error)


def send_event(org_id: int | None, event: str, message: webhooks.Message, server: bool = False) -> None:
    """Send the event to the org's enabled destinations that take it, and to ERROR_WEBHOOK_URL when server is set."""
    if server:
        _send_server(event, message)
    if org_id is None:
        return
    with session() as db:
        org = db.get(Organization, org_id)
        spec = webhooks.EVENTS.get(event)
        if org is None or spec is None:
            return
        if spec.module is not None and not organizations.module_enabled(org, spec.module):
            logger.info("event not sent, its module is off org=%s event=%s module=%s", org_id, event, spec.module)
            return
        rows = db.query(Destination).filter_by(organization_id=org_id, enabled=True).order_by(Destination.id).all()
        rows = [row for row in rows if event in (row.events or [])]
        if not rows:
            return
        if not limits.take(db, org_id, MESSAGES_LIMIT, sub=event):
            logger.info("event over the hourly limit org=%s event=%s", org_id, event)
            return
        db.commit()
        for row in rows:
            target = target_of(row)
            if target is None:
                _record(
                    db,
                    Target(str(row.kind), "", int(row.id), org_id),
                    "event",
                    event,
                    message.title,
                    "The URL cannot be read with SECRETS_KEY. Save the URL again.",
                )
                continue
            deliver(db, target, message, "event", event)


# Each process that imports the send path runs events.deliver with this handler, also on the inline queue
webhooks.on_deliver(send_event)
