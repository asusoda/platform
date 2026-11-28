"""MCP OAuth authorization requests: the request from /authorize, the officer check, consent and the code."""

import datetime
import secrets

from core.config import config, superadmin_ids
from core.integrations.discord import DiscordDirectory, DiscordUnavailable
from core.time import utcnow
from modules.auth import machine_tokens
from modules.auth.scopes import SCOPES
from modules.mcp.models import OAuthRequest
from modules.mcp.oauth import OAuthError, hash_value
from modules.mcp.oauth_clients import touch
from modules.organizations.models import Organization

REQUEST_SECONDS = 600
CODE_SECONDS = 300

_directory: DiscordDirectory | None = None


def start(db, client_id: str, params: dict) -> str:
    """Store a request from /authorize. Returns the sign-in key for the browser cookie. Commits."""
    key = secrets.token_urlsafe(32)
    db.add(
        OAuthRequest(
            client_id=client_id,
            key_hash=hash_value(key),
            redirect_uri=params["redirect_uri"],
            redirect_uri_explicit=params["redirect_uri_provided_explicitly"],
            state=params.get("state"),
            code_challenge=params["code_challenge"],
            requested_scopes=params.get("scopes"),
            resource=params.get("resource"),
            expires_at=utcnow() + datetime.timedelta(seconds=REQUEST_SECONDS),
        )
    )
    touch(db, client_id)
    db.commit()
    return key


def find_request(db, key: str | None, *, signed_in: bool) -> OAuthRequest | None:
    """The open request for a cookie key: before Discord sign-in, or after it when signed_in is True."""
    if not key:
        return None
    row = db.query(OAuthRequest).filter_by(key_hash=hash_value(key)).first()
    if row is None or row.expires_at <= utcnow() or row.code_hash is not None:
        return None
    if (row.discord_id is not None) != signed_in:
        return None
    return row


def discord_directory():
    """The Discord directory that reads officer roles with BOT_TOKEN."""
    global _directory
    if _directory is None:
        _directory = DiscordDirectory(config.BOT_TOKEN)
    return _directory


def officer_orgs(db, discord_id: str, org_id: int | None = None) -> list[Organization]:
    """Active orgs where the member holds the officer role, by name. With org_id, only that org.

    An org whose guild Discord does not answer for is left out. Raises DiscordUnavailable when Discord
    answers for none of them.
    """
    query = db.query(Organization).filter_by(is_active=True)
    if org_id is not None:
        query = query.filter_by(id=org_id)
    orgs = query.order_by(Organization.name).all()
    if discord_id in superadmin_ids():
        return orgs
    directory = discord_directory()
    if not directory.is_ready():
        raise DiscordUnavailable("BOT_TOKEN is not set")
    guilds = {
        str(g) for g in directory.officer_guilds(discord_id, [(str(o.guild_id), o.officer_role_id) for o in orgs])
    }
    return [o for o in orgs if str(o.guild_id) in guilds]


def signed_in(db, row: OAuthRequest, discord_id: str, org_ids: list[int]) -> str:
    """Record the Discord sign-in. Returns the consent key, which replaces the sign-in key. Commits."""
    key = secrets.token_urlsafe(32)
    row.discord_id = discord_id
    row.officer_org_ids = org_ids
    row.key_hash = hash_value(key)
    db.commit()
    return key


def approve(db, row: OAuthRequest, organization_id: int, scopes: list[str], limits: dict | None = None) -> str:
    """Make the authorization code for an approved request. Returns the code. Raises OAuthError. Commits.

    limits is {integration: {name: [items]}}, as on the Connections page.
    """
    if organization_id not in (row.officer_org_ids or []):
        raise OAuthError("Choose an org where you are an officer")
    chosen = sorted(set(scopes) & set(SCOPES))
    if not chosen:
        raise OAuthError("Choose one or more scopes")
    try:
        cleaned = machine_tokens.check_limits(limits)
    except machine_tokens.TokenError as e:
        raise OAuthError(str(e)) from e
    code = secrets.token_urlsafe(32)
    row.organization_id = organization_id
    row.scopes = chosen
    row.limits = cleaned
    row.code_hash = hash_value(code)
    row.key_hash = None
    row.expires_at = utcnow() + datetime.timedelta(seconds=CODE_SECONDS)
    db.commit()
    return code


def deny(db, row: OAuthRequest) -> None:
    db.delete(row)
    db.commit()


def load_code(db, client_id: str, code: str) -> OAuthRequest | None:
    """The approved request of an authorization code that has not expired, or None."""
    row = db.query(OAuthRequest).filter_by(code_hash=hash_value(code), client_id=client_id).first()
    if row is None or row.expires_at <= utcnow() or row.organization_id is None:
        return None
    return row
