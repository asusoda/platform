"""Who is calling, and whether they may act on the organization in the URL.

Officer routes used to accept any valid platform token for any organization. These checks
scope them: a caller may act on an org only if they hold its officer role in Discord, or are
the configured superadmin.

The checks start in report mode. Each request that would be refused logs one
`access decision=would_deny` line and goes through. Setting ACCESS_ENFORCE=true turns those
lines into 403 responses (`decision=deny`). Run in report mode until the log is clean.
"""

import time

import jwt
from flask import current_app, request, session

from modules.utils.logging_config import get_logger
from shared import config, tokenManager

logger = get_logger("access")

OFFICER_CACHE_SECONDS = 60
_officer_cache: dict[str, tuple[float, frozenset[str]]] = {}


class Principal:
    """The caller behind a platform credential."""

    def __init__(self, kind: str, discord_id: str | None):
        self.kind = kind
        self.discord_id = discord_id


def enforcing() -> bool:
    return bool(getattr(config, "ACCESS_ENFORCE", False))


def current_principal() -> Principal | None:
    """Read the platform credential on this request without re-validating it."""
    token = session.get("token")
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer ") and header[7:].strip():
            token = header[7:].strip()
    if not token:
        return None
    try:
        claims = jwt.decode(token, tokenManager.public_key, algorithms=[tokenManager.algorithm])
    except jwt.InvalidTokenError:
        return None
    if "app_name" in claims:
        kind = "app"
    else:
        kind = str(claims.get("type", "untyped"))
    discord_id = claims.get("discord_id")
    return Principal(kind, str(discord_id) if discord_id else None)


def is_superadmin(discord_id: str | None) -> bool:
    superadmin = config.SUPERADMIN_USER_ID
    return bool(discord_id and superadmin and str(discord_id) == str(superadmin))


def officer_guild_ids(discord_id: str) -> frozenset[str] | None:
    """Guild ids where the user holds the officer role, or None if the bot cannot tell."""
    now = time.monotonic()
    cached = _officer_cache.get(discord_id)
    if cached and cached[0] > now:
        return cached[1]
    bot = getattr(current_app, "auth_bot", None)
    if bot is None or not bot.is_ready():
        return None
    guilds = frozenset(str(g) for g in bot.check_officer(discord_id, config.SUPERADMIN_USER_ID))
    _officer_cache[discord_id] = (now + OFFICER_CACHE_SECONDS, guilds)
    return guilds


def clear_cache() -> None:
    _officer_cache.clear()


def _route_org():
    """The organization named in the URL, or None if the route names none or it does not exist."""
    from modules.organizations.models import Organization
    from shared import db_connect

    args = request.view_args or {}
    if "org_prefix" in args:
        criteria = {"prefix": args["org_prefix"]}
    elif "org_id" in args:
        criteria = {"id": args["org_id"]}
    else:
        return None
    db = db_connect.SessionLocal()
    try:
        return db.query(Organization).filter_by(**criteria).first()
    finally:
        db.close()


def _decide(reason: str, principal: Principal | None, org: str | None) -> bool:
    """Log a refusal. Returns True if the request must be refused."""
    enforce = enforcing()
    logger.warning(
        "access decision=%s reason=%s route=%s org=%s credential=%s discord_id=%s",
        "deny" if enforce else "would_deny",
        reason,
        request.url_rule.rule if request.url_rule else request.path,
        org,
        principal.kind if principal else None,
        principal.discord_id if principal else None,
    )
    return enforce


def org_officer_denial() -> tuple[str, int] | None:
    """For a route that names an org, refuse callers who are not its officers.

    Returns (message, status) when the request must be refused, otherwise None.
    """
    org = _route_org()
    if org is None:
        return None
    principal = current_principal()
    if principal is None or not principal.discord_id:
        reason = "no_discord_id" if principal else "no_platform_credential"
        if _decide(reason, principal, org.prefix):
            return "This credential is not tied to a Discord user", 403
        return None
    if is_superadmin(principal.discord_id):
        return None
    guilds = officer_guild_ids(principal.discord_id)
    if guilds is None:
        if _decide("bot_unavailable", principal, org.prefix):
            return "Bot not available for verification", 503
        return None
    if str(org.guild_id) not in guilds:
        if _decide("not_org_officer", principal, org.prefix):
            return "You are not an officer of this organization", 403
    return None


def superadmin_denial(discord_id: str | None) -> tuple[str, int] | None:
    """Refuse callers other than the configured superadmin."""
    if is_superadmin(discord_id):
        return None
    principal = current_principal() or Principal("none", discord_id)
    if _decide("not_superadmin", principal, None):
        return "Superadmin access required!", 403
    return None


def visible_org_filter():
    """Guild ids the caller may list, or None for no restriction.

    In report mode nothing is filtered. In enforce mode officers see only their orgs.
    """
    if not enforcing():
        return None
    principal = current_principal()
    if principal and is_superadmin(principal.discord_id):
        return None
    if principal is None or not principal.discord_id:
        return frozenset()
    return officer_guild_ids(principal.discord_id) or frozenset()
