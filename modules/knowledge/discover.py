"""Pages an agent read: saved as crawled sources, at once for an ASU page and after an officer approves for others.

A page has the key read/<host>/<hash of the URL>. It takes the category of the org's other sources on that host,
or asu or web. A rejected page stays as a disabled source, so the agent does not suggest it again. No Flask here.
"""

import hashlib
import os
from collections import Counter
from urllib.parse import urlsplit, urlunsplit

from core import limits
from modules.knowledge.models import KnowledgeSource
from modules.knowledge.service import KnowledgeError, _find, new_source

PENDING, REJECTED = "pending", "rejected"
DISCOVER_LIMIT = "knowledge.discovered_per_day"
limits.declare(DISCOVER_LIMIT, "knowledge", "Pages agents suggest a day", 200, window="day", unit="pages")


def _every_hours() -> int:
    try:
        value = int(os.environ.get("KNOWLEDGE_DISCOVER_EVERY_HOURS", 168))
    except ValueError:
        return 168
    return value if 1 <= value <= 24 * 30 else 168


def _auto_hosts() -> tuple[str, ...]:
    """The domains whose pages are saved without review, from KNOWLEDGE_DISCOVER_AUTO."""
    raw = os.environ.get("KNOWLEDGE_DISCOVER_AUTO", "asu.edu")
    return tuple(h.strip().lower().lstrip(".") for h in raw.split(",") if h.strip())


def _automatic(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in _auto_hosts())


def normalize(url: object) -> tuple[str, str]:
    """The URL with no fragment and a lowercase host, and that host. Raises KnowledgeError for any other URL."""
    if not isinstance(url, str) or not url.strip() or len(url) > 2000:
        raise KnowledgeError("url must be a string of at most 2000 characters")
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host or "." not in host:
        raise KnowledgeError("url must be an http or https address with a host name")
    if parts.username or parts.password:
        raise KnowledgeError("url must not hold a user name or password")
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, "")), host


def _category(db, org_id: int, host: str) -> str:
    """The most common category of the org's sources on host, or asu or web."""
    found = Counter(
        category
        for url, category in db.query(KnowledgeSource.url, KnowledgeSource.category)
        .filter(KnowledgeSource.organization_id == org_id, KnowledgeSource.url.isnot(None))
        .all()
        if (urlsplit(str(url)).hostname or "").lower() == host
    )
    if found:
        return found.most_common(1)[0][0]
    return "asu" if host == "asu.edu" or host.endswith(".asu.edu") else "web"


def discover(db, org_id: int, url: object) -> dict:
    """Save a page an agent read as a crawled source of the org. Commits.

    status is known when the org has a source with that URL, added when the page is saved, and review when it
    waits on an officer.
    """
    page, host = normalize(url)
    known = db.query(KnowledgeSource).filter_by(organization_id=org_id, url=page).first()
    if known is not None:
        return {"key": known.key, "status": "known"}
    limits.consume(db, org_id, DISCOVER_LIMIT)
    key = f"read/{host[:200]}/{hashlib.sha256(page.encode()).hexdigest()[:12]}"
    auto = _automatic(host)
    new_source(
        db,
        org_id,
        key=key,
        url=page,
        category=_category(db, org_id, host),
        fetch_every_hours=_every_hours(),
        enabled=auto,
        review=None if auto else PENDING,
    )
    db.commit()
    return {"key": key, "status": "added" if auto else "review"}


def review(db, org_id: int, key: str, approve: object) -> dict:
    """Approve or reject a page that waits on an officer. Approving starts its crawl on the next run. Commits."""
    if not isinstance(approve, bool):
        raise KnowledgeError("approve must be true or false")
    source = _find(db, org_id, key)
    if source.review is None:
        raise KnowledgeError("This source is not waiting on a review", 409)
    source.review, source.enabled = (None, True) if approve else (REJECTED, False)
    source.last_attempt_at = None
    db.commit()
    return {"key": key, "review": source.review, "enabled": bool(source.enabled)}
