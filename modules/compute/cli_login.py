"""Member credentials for the compute CLI. No Flask here.

A member signs in with Discord in the browser and gets a machine token of kind cli with the
scope compute:connect, bound to their Discord id and the org. The CLI sends it as a bearer token
on the member routes. A new token replaces the member's previous one.
"""

import datetime

from modules.auth import machine_tokens, scopes
from modules.auth.models import MachineToken

scopes.declare(
    "compute:connect", "List the compute pods shared with a member and connect to them (compute CLI)", uses=("runpod",)
)

SCOPE = "compute:connect"
KIND = "cli"
EXPIRES_DAYS = 90


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
        name="compute cli",
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
