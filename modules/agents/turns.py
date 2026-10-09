"""One read and one write per agent turn. No Flask here.

An agent reads the turn context before it calls its model, and commits the turn
after it answers. The context holds who the member is in the org (from Discord, never from the
agent), the conversation so far, memories and the profile graph. The commit writes the new
messages, summary, memories, facts and pending actions in one transaction, so a failed turn
leaves nothing half written.
"""

from typing import Any

from core.integrations.discord import DiscordUnavailable
from modules.agents import conversations, memories, pending, profile, service
from modules.agents.service import AgentError, Owner
from modules.knowledge.embedder import Embedder

MAX_ITEMS = 100


def member(directory: Any, guild_id: object, officer_role_id: object, discord_id: str) -> dict:
    """The member as Discord reports them in the org's server. Raises AgentError when they are not in it."""
    if directory is None or not directory.is_ready():
        raise AgentError("Discord is not configured, so membership cannot be checked", 503)
    try:
        row = directory.get_member(guild_id, discord_id)
    except DiscordUnavailable as e:
        raise AgentError("Discord could not be reached to check membership", 503) from e
    if not row:
        raise AgentError("This Discord user is not a member of the organization", 403)
    user = row.get("user") or {}
    roles = [str(r) for r in row.get("roles") or []]
    return {
        "discord_id": discord_id,
        "display_name": row.get("nick") or user.get("global_name") or user.get("username"),
        "roles": roles,
        "officer": bool(officer_role_id) and str(officer_role_id) in roles,
    }


def _int(value: object, name: str, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AgentError(f"{name} must be a non-negative integer")
    return min(value, service.MAX_LIMIT)


def context(db, who: Owner, member_info: dict, data: dict, embedder: Embedder | None = None) -> dict:
    """Everything an agent needs before it calls its model, in one read.

    data: conversation_id, visibility, and optional message_limit, memory_kinds, memory_limit,
    profile_limit, and profile_query (text whose nearest profile nodes come back as
    profile.similar when an embedder is configured). A limit of 0 leaves that part out.
    """
    conversation_id = data.get("conversation_id")
    visibility = data.get("visibility")
    if visibility not in service.VISIBILITIES:
        raise AgentError(f"visibility must be one of {', '.join(service.VISIBILITIES)}")
    message_limit = _int(data.get("message_limit"), "message_limit", 50)
    memory_limit = _int(data.get("memory_limit"), "memory_limit", 20)
    profile_limit = _int(data.get("profile_limit"), "profile_limit", 100)

    owned = conversations.owns(db, who, conversation_id, visibility)
    profile_query = data.get("profile_query")
    similar = []
    if profile_query is not None and embedder is not None and profile_limit:
        similar = profile.similar(db, who, profile_query, min(profile_limit, 20), embedder)
    return {
        "member": member_info,
        "conversation": {"id": conversation_id, "owned": owned},
        "messages": conversations.load(db, who, conversation_id, message_limit) if owned and message_limit else [],
        "memories": memories.recall(db, who, data.get("memory_kinds"), memory_limit) if memory_limit else [],
        "profile": {
            "nodes": profile.profile_nodes(db, who, profile_limit) if profile_limit else [],
            "relations": profile.relations(db, who, profile_limit) if profile_limit else [],
            "similar": similar,
        },
    }


def _list(data: dict, name: str) -> list:
    value = data.get(name)
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        raise AgentError(f"{name} must be a list of at most {MAX_ITEMS}")
    return value


def commit(db, who: Owner, data: dict, embedder: Embedder | None = None) -> dict:
    """Write one turn in one transaction: conversation, messages, summary, memories, facts, pending actions.

    Nothing is written when any part is invalid. Commits.
    """
    conversation_id = data.get("conversation_id")
    messages = _list(data, "messages")
    memory_items = _list(data, "memories")
    facts = _list(data, "facts")
    held = _list(data, "pending")
    summary = data.get("summary")
    if summary is not None and not isinstance(summary, dict):
        raise AgentError("summary must be an object with content and covers")
    if not (messages or summary or memory_items or facts or held):
        raise AgentError("Nothing to commit")

    try:
        cid = conversations.ensure(
            db, who, conversation_id, data.get("channel_id"), data.get("visibility"), commit=False
        )
        seqs = conversations.append(db, who, cid, messages, commit=False) if messages else []
        summary_seq = (
            conversations.append_summary(db, who, cid, summary.get("content"), summary.get("covers"), commit=False)
            if summary
            else None
        )
        saved = []
        for m in memory_items:
            if not isinstance(m, dict):
                raise AgentError("each memory must be an object")
            optional = ("sensitivity", "confidence", "source_seq", "expires_in_days")
            given = {k: m[k] for k in optional if k in m}
            row = memories.remember(db, who, kind=m.get("kind"), content=m.get("content"), commit=False, **given)
            saved.append(row["id"])
        fact_count = profile.upsert(db, who, facts, commit=False, embedder=embedder) if facts else 0
        for p in held:
            if not isinstance(p, dict):
                raise AgentError("each pending action must be an object")
            pending.hold(
                db,
                who,
                p.get("token"),
                p.get("action"),
                p.get("payload_hash"),
                p.get("ttl_seconds", 600),
                commit=False,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "conversation_id": cid,
        "seqs": seqs,
        "summary_seq": summary_seq,
        "memory_ids": saved,
        "facts": fact_count,
        "pending": len(held),
    }
