"""Unresolved Sentry issues for the Activity page and agents. No Flask here.

Reads the org's Sentry integration. Responses are cached per org for CACHE_SECONDS.
"""

import time
from typing import cast

from core.integrations import registry, sentry
from modules.organizations.models import Organization

CACHE_SECONDS = 60
MAX_ISSUES = 50
registry.use(sentry.KEY, "dashboard")

# org id: (expiry, the limit fetched, the result)
_cache: dict[int, tuple[float, int, dict]] = {}


def _issue(raw: dict) -> dict:
    return {
        "id": raw.get("id"),
        "short_id": raw.get("shortId"),
        "title": raw.get("title"),
        "culprit": raw.get("culprit"),
        "level": raw.get("level"),
        "count": int(raw.get("count") or 0),
        "users": int(raw.get("userCount") or 0),
        "first_seen": raw.get("firstSeen"),
        "last_seen": raw.get("lastSeen"),
        "url": raw.get("permalink"),
    }


def issues(db, org: Organization, limit: int = 25) -> dict:
    """The newest unresolved issues of the org's Sentry project, or the reason there are none."""
    org_id = cast(int, org.id)
    conf = sentry.settings(db, org_id)
    if conf is None:
        return {"configured": False, "issues": [], "error": None, "project_url": None}
    limit = max(1, min(limit, MAX_ISSUES))
    now = time.monotonic()
    cached = _cache.get(org_id)
    if cached and cached[0] > now and cached[1] >= limit:
        return {**cached[2], "issues": cached[2]["issues"][:limit]}
    project_url = f"{conf['url']}/organizations/{conf['org']}/issues/?query=is%3Aunresolved"
    try:
        raw = sentry.get(conf, "issues/", {"query": "is:unresolved", "statsPeriod": "14d", "limit": limit})
    except sentry.SentryError as e:
        return {"configured": True, "issues": [], "error": str(e), "project_url": project_url}
    found = [_issue(i) for i in raw if isinstance(i, dict)] if isinstance(raw, list) else []
    result = {"configured": True, "issues": found, "error": None, "project_url": project_url}
    _cache[org_id] = (now + CACHE_SECONDS, limit, result)
    return result


def clear_cache() -> None:
    _cache.clear()
