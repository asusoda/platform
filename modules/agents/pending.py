"""Pending actions: consequential tool calls held until the member confirms or denies them. No Flask here."""

import datetime

from core.time import utcnow
from modules.agents import service
from modules.agents.models import AgentPendingAction
from modules.agents.service import AgentError, Owner


def hold(
    db,
    who: Owner,
    token: object,
    action: object,
    payload_hash: object,
    ttl_seconds: object = 600,
    *,
    commit: bool = True,
) -> None:
    """Hold an action until the member confirms or denies it. token is a UUID the agent chose. Commits unless commit is false."""
    tid = service.uuid_text(token)
    if not isinstance(action, dict):
        raise AgentError("action must be an object")
    digest = service.text(payload_hash, "payload_hash", 128)
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= 86400:
        raise AgentError("ttl_seconds must be from 1 to 86400")
    if db.query(AgentPendingAction).filter_by(id=tid).first() is not None:
        raise AgentError("token is already used", 409)
    db.add(
        AgentPendingAction(
            id=tid,
            organization_id=who.organization_id,
            discord_id=who.discord_id,
            action=action,
            payload_hash=digest,
            agent_token_id=who.token_id,
            expires_at=utcnow() + datetime.timedelta(seconds=ttl_seconds),
        )
    )
    service.save(db, commit)


def claim(db, who: Owner, token: object, approved: object) -> dict | None:
    """Confirm or deny a held action once. Returns {"action", "payload_hash"} or None when it is
    unknown, another member's, expired, or already answered. Commits."""
    if not isinstance(approved, bool):
        raise AgentError("approved must be true or false")
    tid = service.uuid_text(token)
    now = utcnow()
    claimed = (
        db.query(AgentPendingAction)
        .filter(
            AgentPendingAction.id == tid,
            AgentPendingAction.organization_id == who.organization_id,
            AgentPendingAction.discord_id == who.discord_id,
            AgentPendingAction.status == "pending",
            AgentPendingAction.expires_at > now,
        )
        .update({"status": "confirmed" if approved else "denied", "resolved_at": now}, synchronize_session=False)
    )
    db.commit()
    if not claimed:
        return None
    row = db.query(AgentPendingAction).filter_by(id=tid).one()
    return {"action": row.action, "payload_hash": row.payload_hash}
