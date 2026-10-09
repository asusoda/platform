"""The error log for officers: the org's errors, resolve and reopen, dashboard reports, and Discord alerts.

core/error_log.py stores the errors. setup() installs its handler in a process and adds the org lookup and
the Discord alert. A new error group, or a resolved one that comes back, posts one message to the org's
webhook (org secret error_webhook_url) and to ERROR_WEBHOOK_URL from .env, at most ALERTS_PER_HOUR per
process. No Flask here.
"""

import os
import re
import threading
import time
from typing import cast

import requests
from sqlalchemy import or_

from core import error_log, secrets
from core.db import session
from core.errors import ServiceError
from core.log import get_logger
from modules.organizations.models import Organization

logger = get_logger("error_alerts")

WEBHOOK_SECRET = "error_webhook_url"  # nosec B105 - the name of an org secret, not its value
WEBHOOK_PATTERN = re.compile(r"^https://(?:discord|discordapp)\.com/api/webhooks/\d+/[\w-]+$")
ALERTS_PER_HOUR = 30
MAX_REPORT_FIELD = 5000
LEVEL_COLOR = 0xE5484D

secrets.declare(WEBHOOK_SECRET, "Discord webhook URL that gets a message for each new error")

_sent: list[float] = []
_sent_lock = threading.Lock()


class ErrorLogError(ServiceError, ValueError):
    pass


def _org_prefix(value: str | None) -> str | None:
    """The org prefix for a prefix, an org id or a guild id from a request, else the value."""
    if not value or not value.isdigit():
        return value
    with session() as db:
        org = db.query(Organization).filter(or_(Organization.id == int(value), Organization.guild_id == value)).first()
        return str(org.prefix) if org is not None else value


def _allow_alert() -> bool:
    now = time.monotonic()
    with _sent_lock:
        _sent[:] = [t for t in _sent if now - t < 3600]
        if len(_sent) >= ALERTS_PER_HOUR:
            return False
        _sent.append(now)
        return True


def _message(group: dict) -> dict:
    where = " · ".join(p for p in (group["source"], group.get("org"), group.get("route") or group.get("location")) if p)
    return {
        "embeds": [
            {
                "title": f"{group['kind']}"[:256],
                "description": f"{group['message']}"[:1500],
                "color": LEVEL_COLOR,
                "footer": {"text": f"{where}"[:2048]},
            }
        ],
        "allowed_mentions": {"parse": []},
    }


def _post(url: str, payload: dict) -> None:
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code >= 400:
            logger.warning("error alert refused status=%s", response.status_code)
    except requests.RequestException:
        logger.warning("error alert could not reach Discord")


def _alert(group: dict) -> None:
    """Post a new or returning error group to the Discord webhooks, in a background thread."""
    urls = []
    if group.get("org"):
        with session() as db:
            org = db.query(Organization).filter(Organization.prefix == group["org"]).first()
            if org is not None:
                url = secrets.get_secret(db, cast(int, org.id), WEBHOOK_SECRET)
                if url:
                    urls.append(url)
    if os.environ.get("ERROR_WEBHOOK_URL"):
        urls.append(os.environ["ERROR_WEBHOOK_URL"])
    if not urls or not _allow_alert():
        return
    payload = _message(group)
    for url in dict.fromkeys(urls):
        threading.Thread(target=_post, args=(url, payload), daemon=True).start()


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
        "webhook_set": bool(secrets.get_secret(db, cast(int, org.id), WEBHOOK_SECRET)),
    }


def _ids(value: object) -> list[int]:
    if not isinstance(value, list) or not value or len(value) > 200 or not all(isinstance(i, int) for i in value):
        raise ErrorLogError("ids must be a list of 1 to 200 error ids")
    return cast(list[int], value)


def resolve(db, org: Organization, ids: object, actor: str | None) -> dict:
    return {"changed": error_log.set_resolved(db, _ids(ids), resolved=True, actor=actor, org=str(org.prefix))}


def reopen(db, org: Organization, ids: object) -> dict:
    return {"changed": error_log.set_resolved(db, _ids(ids), resolved=False, actor=None, org=str(org.prefix))}


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
        kind=cast(str, fields["kind"])[:200] or "Error",
        message=cast(str, fields["message"])[:MAX_REPORT_FIELD],
        stack=cast(str | None, fields["stack"]),
        location=page[:255] if page else None,
        org=str(org.prefix),
        route=page[:255] if page else None,
        group_key=cast(str, fields["message"])[:200],
    )
    return {"recorded": True}


def set_webhook(db, org: Organization, url: object, actor: str | None) -> dict:
    """Set or clear the org's error alert webhook. The URL is never returned."""
    if url is not None and (not isinstance(url, str) or not WEBHOOK_PATTERN.match(url)):
        raise ErrorLogError("Use a Discord webhook URL: https://discord.com/api/webhooks/...")
    org_id = cast(int, org.id)
    if url is None:
        secrets.delete_secret(db, org_id, WEBHOOK_SECRET)
        db.commit()
        return {"webhook_set": False}
    try:
        secrets.set_secret(db, org_id, WEBHOOK_SECRET, url, updated_by=actor)
    except secrets.SecretsError as e:
        raise ErrorLogError(str(e)) from e
    return {"webhook_set": True}
