"""Who is on a pod: the member picker, who may connect, who got a certificate and who is connected now."""

from collections.abc import Callable
from typing import cast

from core import hosting
from core.errors import ServiceError
from core.log import get_logger
from modules.godfather import base
from modules.godfather.models import ComputeConnection

logger = get_logger(__name__)

RECENT_CONNECTIONS = 100
# The most names one request looks up in the member directory.
NAME_LOOKUPS = 50


def member_page(directory, guild_id, query: str = "", role: str = "", limit: int = 50) -> dict:
    """Server members for the allowed members picker, sorted by name. Bots are left out.

    A query searches names through Discord. Without one, the whole member list is read. role keeps the members
    that hold that role. total counts every match; members holds the first limit.
    """
    if query:
        found = directory.search_members(guild_id, query, 100)
    else:
        found = directory.list_members(guild_id)
    matches = [m for m in found if not m.get("bot") and (not role or role in m.get("roles", []))]
    matches.sort(key=lambda m: (str(m["name"]).casefold(), m["id"]))
    return {"members": matches[:limit], "total": len(matches)}


def _named(ids: list[str], name_of: Callable[[str], str | None] | None) -> dict[str, str | None]:
    """Display names for the first NAME_LOOKUPS ids. The others, and ids name_of does not know, get None."""
    names: dict[str, str | None] = dict.fromkeys(ids)
    if name_of is not None:
        for discord_id in ids[:NAME_LOOKUPS]:
            names[discord_id] = name_of(discord_id)
    return names


def _recent(db, org_id: int, pod_id: str) -> list[ComputeConnection]:
    query = db.query(ComputeConnection).filter_by(organization_id=org_id, pod_id=pod_id)
    return (
        query.order_by(ComputeConnection.created_at.desc(), ComputeConnection.id.desc()).limit(RECENT_CONNECTIONS).all()
    )


def pod_members(db, org_id: int, pod_id: str, name_of: Callable[[str], str | None] | None = None) -> dict:
    """Who may connect to a pod and who got a certificate for it, newest first.

    name_of gives a member's display name from a Discord id, or None.
    """
    row = base.find_pod(db, org_id, pod_id)
    allowed = list(cast(list, row.allowed_users) or [])
    recent = _recent(db, org_id, pod_id)
    ids = list(dict.fromkeys([*(str(c.discord_id) for c in recent), *allowed]))
    names = _named(ids, name_of)
    return {
        "pod_id": pod_id,
        "access": {
            "is_public": bool(row.is_public),
            "allowed": [{"discord_id": i, "name": names.get(i)} for i in allowed],
        },
        "recent": [
            {
                "discord_id": c.discord_id,
                "name": names.get(str(c.discord_id)),
                "username": c.username,
                "is_admin": bool(c.is_admin),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in recent
        ],
    }


def connected_now(
    db,
    org_id: int,
    pod_id: str,
    name_of: Callable[[str], str | None] | None = None,
    client: hosting.HostingClient | None = None,
    reader: Callable[[str, int, str], list[dict]] | None = None,
) -> dict:
    """The live SSH sessions on a pod. state is known or unknown; an unknown state has a reason and no sessions.

    reader takes host, port and the backend private key and returns the sessions from presence.sessions.
    """
    from modules.godfather import presence

    row = base.find_pod(db, org_id, pod_id)
    try:
        live = base.call((client or base.get_client(db, org_id, str(row.provider))).get_pod, pod_id)
        if base.pod_status(live, str(row.provider)) != "RUNNING":
            return {"pod_id": pod_id, "state": "unknown", "reason": "The pod is not running", "sessions": []}
        address = base.provider_of(row).ssh_address(cast(dict, live))
        if address is None:
            return {"pod_id": pod_id, "state": "unknown", "reason": "The pod has no SSH address yet", "sessions": []}
        _, backend_private = base.keypair(db, org_id, base.BACKEND_KEY)
        found = (reader or presence.sessions)(address[0], address[1], backend_private)
    except ServiceError as e:
        logger.info("godfather presence unknown org=%s pod=%s: %s", org_id, pod_id, e.message)
        return {"pod_id": pod_id, "state": "unknown", "reason": e.message, "sessions": []}
    # A username maps to the member who last got a certificate with it for this pod
    owners: dict[str, str] = {}
    for c in reversed(_recent(db, org_id, pod_id)):
        owners[str(c.username)] = str(c.discord_id)
    names = _named(list(dict.fromkeys(owners[s["username"]] for s in found if s["username"] in owners)), name_of)
    sessions = [
        s | {"discord_id": owners.get(s["username"]), "name": names.get(owners.get(s["username"], ""))} for s in found
    ]
    return {"pod_id": pod_id, "state": "known", "reason": None, "sessions": sessions}
