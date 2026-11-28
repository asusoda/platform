"""MCP OAuth grants: the code exchange, refresh with the officer check, revocation and the cleanup of old rows."""

import datetime
import secrets
from typing import cast

from core import audit
from core.integrations.discord import DiscordUnavailable
from core.log import get_logger
from core.time import utcnow
from modules.auth import machine_tokens
from modules.auth.models import MachineToken
from modules.mcp.models import OAuthClient, OAuthGrant, OAuthRequest
from modules.mcp.oauth import INVALID_SCOPE, OAuthError, epoch, hash_value, optional_text, strings
from modules.mcp.oauth_clients import client_name, touch
from modules.mcp.oauth_requests import load_code, officer_orgs

ACCESS_SECONDS = 3600
REFRESH_DAYS = 30
REFRESH_PREFIX = "platr_"
# A refresh needs a new check of the officer role. If Discord does not answer, a check this recent is enough
RECHECK_GRACE = datetime.timedelta(hours=24)

logger = get_logger(__name__)


def _token(access: str, refresh: str, scopes: list[str]) -> dict:
    return {
        "access_token": access,
        "expires_in": ACCESS_SECONDS,
        "scope": " ".join(scopes),
        "refresh_token": refresh,
    }


def exchange_code(db, client_id: str, code: str) -> dict:
    """Use an authorization code once and make the grant. Raises OAuthError. Commits."""
    row = load_code(db, client_id, code)
    if row is None:
        raise OAuthError("The authorization code is not valid, has expired or was used before")
    # The delete finds the row only once, so a code that two requests send gives one grant
    if db.query(OAuthRequest).filter_by(id=row.id, code_hash=row.code_hash).delete() != 1:
        db.rollback()
        raise OAuthError("The authorization code was used before")
    client = db.query(OAuthClient).filter_by(client_id=client_id).first()
    name = client_name(dict(client.info)) if client is not None else "MCP client"
    access, token_row = machine_tokens.issue_oauth(
        db,
        organization_id=cast(int, row.organization_id),
        name=name,
        scopes=strings(row.scopes),
        created_by=str(row.discord_id),
        expires_seconds=ACCESS_SECONDS,
        limits=cast(dict, row.limits) or None,
    )
    refresh = REFRESH_PREFIX + secrets.token_urlsafe(32)
    db.add(
        OAuthGrant(
            machine_token_id=token_row.id,
            client_id=client_id,
            refresh_hash=hash_value(refresh),
            refresh_expires_at=utcnow() + datetime.timedelta(days=REFRESH_DAYS),
            resource=row.resource,
            scopes=strings(token_row.scopes),
        )
    )
    touch(db, client_id)
    db.commit()
    return _token(access, refresh, strings(token_row.scopes))


def _granted_scopes(grant: OAuthGrant, token: MachineToken) -> list[str]:
    """The scopes of the grant, which a refresh can narrow for one access token but never changes."""
    return strings(grant.scopes) if grant.scopes is not None else strings(token.scopes)


def _grant_for_refresh(db, client_id: str, refresh: str) -> tuple[OAuthGrant, MachineToken] | None:
    if not refresh.startswith(REFRESH_PREFIX):
        return None
    grant = db.query(OAuthGrant).filter_by(refresh_hash=hash_value(refresh), client_id=client_id).first()
    if grant is None or grant.refresh_expires_at <= utcnow():
        return None
    token = db.query(MachineToken).filter_by(id=grant.machine_token_id).first()
    if token is None or token.revoked_at is not None:
        return None
    return grant, token


def load_refresh(db, client_id: str, refresh: str) -> dict | None:
    """The fields of the SDK's refresh token for a live grant, or None."""
    found = _grant_for_refresh(db, client_id, refresh)
    if found is None:
        return None
    grant, token = found
    return {
        "token_id": token.id,
        "scopes": _granted_scopes(grant, token),
        "expires_at": epoch(grant.refresh_expires_at),
        "resource": optional_text(grant.resource),
        "subject": optional_text(token.created_by),
    }


def exchange_refresh(db, client_id: str, refresh: str, scopes: list[str]) -> dict:
    """New access and refresh tokens for a grant. The old values stop working. Raises OAuthError. Commits.

    The access token gets scopes, or all the scopes of the grant when scopes is empty. A scope outside the grant
    raises OAuthError(INVALID_SCOPE). The grant's scopes change only when an officer approves it.
    """
    found = _grant_for_refresh(db, client_id, refresh)
    if found is None:
        raise OAuthError("The refresh token is not valid, has expired or its connection was revoked")
    grant, token = found
    now = utcnow()
    checked = _still_officer(db, token)
    if checked is False:
        machine_tokens.revoke(db, token.organization_id, token.id)
        audit.record(
            "mcp oauth revoked",
            source="mcp",
            actor_kind="system",
            actor_id=optional_text(token.created_by),
            details={"client_id": client_id, "token_id": token.id, "reason": "not_officer"},
        )
        raise OAuthError("The officer who approved this connection is no longer an officer of the org")
    if checked is None and grant.checked_at <= now - RECHECK_GRACE:
        raise OAuthError("Platform cannot check the officer role now. Try again later")
    granted = _granted_scopes(grant, token)
    if set(scopes) - set(granted):
        raise OAuthError(INVALID_SCOPE)
    new_refresh = REFRESH_PREFIX + secrets.token_urlsafe(32)
    # The update finds the old hash only once, so a refresh token that two requests send rotates once
    changed = (
        db.query(OAuthGrant)
        .filter_by(id=grant.id, refresh_hash=grant.refresh_hash)
        .update(
            {
                "refresh_hash": hash_value(new_refresh),
                "refresh_expires_at": now + datetime.timedelta(days=REFRESH_DAYS),
                # A grant from before grants kept their scopes gets the scopes it was approved with
                **({"scopes": granted} if grant.scopes is None else {}),
                **({"checked_at": now} if checked else {}),
            }
        )
    )
    if changed != 1:
        db.rollback()
        raise OAuthError("The refresh token was used before")
    access = machine_tokens.rotate(db, token, ACCESS_SECONDS, scopes or granted)
    touch(db, client_id)
    db.commit()
    return _token(access, new_refresh, strings(token.scopes))


def _still_officer(db, token: MachineToken) -> bool | None:
    """Whether the officer who approved the token still has the officer role in its org. None if Discord cannot tell."""
    try:
        orgs = officer_orgs(db, str(token.created_by), int(token.organization_id))
    except DiscordUnavailable:
        logger.warning(
            "officer check of an MCP OAuth refresh skipped: Discord unavailable token_id=%s org_id=%s",
            token.id,
            token.organization_id,
            exc_info=True,
        )
        return None
    return token.organization_id in {o.id for o in orgs}


def client_of_token(db, token_id: int) -> str | None:
    """The OAuth client id of a machine token, or None for a token that an officer made."""
    grant = db.query(OAuthGrant).filter_by(machine_token_id=token_id).first()
    return str(grant.client_id) if grant is not None else None


def revoke(db, token_id: int) -> None:
    """Revoke the machine token of a grant. Its access and refresh tokens stop working. Commits."""
    row = db.query(MachineToken).filter_by(id=token_id).first()
    if row is not None:
        machine_tokens.revoke(db, int(row.organization_id), token_id)


def cleanup(db) -> dict:
    """Delete old requests, finished grants and unused clients. Commits."""
    now = utcnow()
    requests = db.query(OAuthRequest).filter(OAuthRequest.expires_at <= now).delete(synchronize_session=False)
    finished = [
        (grant.id, grant.machine_token_id, token.organization_id if token is not None else None)
        for grant, token in db.query(OAuthGrant, MachineToken).outerjoin(
            MachineToken, MachineToken.id == OAuthGrant.machine_token_id
        )
        if token is None or token.revoked_at is not None or grant.refresh_expires_at <= now
    ]
    # An expired grant leaves no live token on the Connections page, and no live token that it issued
    db.query(MachineToken).filter(
        MachineToken.id.in_([token_id for _, token_id, _ in finished]), MachineToken.revoked_at.is_(None)
    ).update({"revoked_at": now}, synchronize_session=False)
    by_org: dict[int, list[int]] = {}
    for _, token_id, org_id in finished:
        if org_id is not None:
            by_org.setdefault(int(org_id), []).append(int(token_id))
    for org_id, token_ids in by_org.items():
        machine_tokens.revoke_children(db, org_id, token_ids)
    db.query(OAuthGrant).filter(OAuthGrant.id.in_([grant_id for grant_id, _, _ in finished])).delete(
        synchronize_session=False
    )
    in_use = db.query(OAuthGrant.client_id)
    unused = (
        db.query(OAuthClient)
        .filter(OAuthClient.last_used_at <= now - datetime.timedelta(days=7), ~OAuthClient.client_id.in_(in_use))
        .delete(synchronize_session=False)
    )
    # A document client with no grant and no open request is only a cache: delete it now, not after 7 days
    open_requests = db.query(OAuthRequest.client_id)
    documents = (
        db.query(OAuthClient)
        .filter(
            OAuthClient.cache_until.isnot(None),
            ~OAuthClient.client_id.in_(in_use),
            ~OAuthClient.client_id.in_(open_requests),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"requests": requests, "grants": len(finished), "clients": unused + documents}
