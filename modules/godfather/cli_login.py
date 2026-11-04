"""Member credentials for the Godfather CLI. No Flask here.

A member signs in with Discord in the browser and gets a machine token of kind cli with the
scope godfather:connect, bound to their Discord id and the org. The CLI sends it as a bearer token
on the member routes. A new token replaces the member's previous one.

A CLI that listens on 127.0.0.1 gets the token without a paste: the callback sends the browser to
the CLI with a one-time code, and the CLI redeems the code with its PKCE verifier (RFC 7636, S256).
"""

import base64
import datetime
import hashlib
import hmac
import re
import secrets

from core.errors import ServiceError
from core.time import utcnow
from modules.auth import machine_tokens, scopes
from modules.auth.models import MachineToken
from modules.godfather.models import ComputeCliCode

scopes.declare(
    "godfather:connect",
    "List the Godfather pods shared with a member and connect to them (Godfather CLI)",
    uses=("runpod",),
)

SCOPE = "godfather:connect"
KIND = "cli"
EXPIRES_DAYS = 90
CODE_LIFETIME = datetime.timedelta(minutes=2)

STATE_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
CHALLENGE_RE = re.compile(r"^[A-Za-z0-9_-]{43,128}$")


def issue(db, org_id: int, discord_id: str) -> str:
    """A fresh CLI token for this member, revoking their older ones. Commits."""
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    db.query(MachineToken).filter(
        MachineToken.organization_id == org_id,
        MachineToken.kind == KIND,
        MachineToken.created_by == discord_id,
        MachineToken.revoked_at.is_(None),
    ).update({"revoked_at": now}, synchronize_session=False)
    value, _ = machine_tokens.issue(
        db,
        organization_id=org_id,
        name="godfather cli",
        kind=KIND,
        scopes=[SCOPE],
        created_by=discord_id,
        expires_days=EXPIRES_DAYS,
    )
    return value


def member_for(db, org_id: int, token: str | None) -> str | None:
    """The Discord id a CLI token stands for in this org, or None."""
    caller = machine_tokens.verify(db, token)
    if caller is None or caller.kind != KIND or not caller.allows(SCOPE):
        return None
    if caller.organization_id != org_id or not caller.created_by:
        return None
    return caller.created_by


def loopback(port: object, state: object, challenge: object, method: object) -> dict | None:
    """The loopback sign-in parameters, None when none are sent. Raises ServiceError for a partial or bad set."""
    values = (port, state, challenge, method)
    if all(v is None for v in values):
        return None
    try:
        number = int(str(port))
    except ValueError:
        number = 0
    if not 1024 <= number <= 65535:
        raise ServiceError("port must be a number from 1024 to 65535")
    if not isinstance(state, str) or not STATE_RE.match(state):
        raise ServiceError("state must be 8 to 128 URL-safe characters")
    if not isinstance(challenge, str) or not CHALLENGE_RE.match(challenge):
        raise ServiceError("code_challenge must be 43 to 128 URL-safe characters")
    if method != "S256":
        raise ServiceError("code_challenge_method must be S256")
    return {"port": number, "state": state, "code_challenge": challenge}


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def challenge_for(verifier: str) -> str:
    """The S256 code challenge of a PKCE verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def start_code(db, org_id: int, discord_id: str, code_challenge: str, now=None) -> str:
    """A one-time code for this member that works for CODE_LIFETIME. Deletes expired codes. Commits."""
    now = now or utcnow()
    db.query(ComputeCliCode).filter(ComputeCliCode.expires_at <= now).delete(synchronize_session=False)
    code = secrets.token_urlsafe(32)
    db.add(
        ComputeCliCode(
            organization_id=org_id,
            discord_id=discord_id,
            code_hash=_hash(code),
            code_challenge=code_challenge,
            expires_at=now + CODE_LIFETIME,
        )
    )
    db.commit()
    return code


def redeem(db, org_id: int, code: object, code_verifier: object, now=None) -> tuple[str, str]:
    """Trade a code and its verifier for (token, discord id). The code works once. Commits."""
    if not isinstance(code, str) or not code or not isinstance(code_verifier, str) or not code_verifier:
        raise ServiceError("code and code_verifier are required")
    now = now or utcnow()
    row = db.query(ComputeCliCode).filter_by(organization_id=org_id, code_hash=_hash(code)).first()
    if row is None or row.expires_at <= now:
        raise ServiceError("The sign-in code is invalid or expired. Sign in again.")
    discord_id = str(row.discord_id)
    matches = hmac.compare_digest(challenge_for(code_verifier), str(row.code_challenge))
    db.delete(row)
    db.commit()
    if not matches:
        raise ServiceError("The sign-in code is invalid or expired. Sign in again.")
    return issue(db, org_id, discord_id), discord_id
