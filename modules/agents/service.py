"""Storage for agents: conversations, memories, the profile graph and pending actions. No Flask here.

Every function is scoped to one Owner: the machine token's organization plus the Discord id of the
member the agent is talking to. The agent says who the member is; the platform checks the token, so
an agent can only reach members of its own organization.

Sensitive memories are encrypted with the same Fernet keys as org secrets (SECRETS_KEY).
"""

import datetime
import math
import os
import uuid
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import func, or_, text

from core import secrets
from core.errors import ServiceError
from core.log import get_logger
from core.time import iso, utcnow
from modules.agents.models import (
    AgentConversation,
    AgentMemory,
    AgentMessage,
    AgentPendingAction,
    AgentProfileEdge,
    AgentProfileNode,
)
from modules.auth import scopes
from modules.knowledge.embedder import Embedder, EmbeddingError
from modules.knowledge.models import DIMENSIONS, Embedding

logger = get_logger("agents")

VISIBILITIES = ("public", "private")
ROLES = ("system", "user", "assistant", "tool")
MEMORY_KINDS = ("episodic", "semantic", "profile", "task")
SENSITIVITIES = ("normal", "sensitive")
MAX_LIMIT = 500

scopes.declare("agents:read", "Read conversations, memories and profiles of members the agent talks to")
scopes.declare("agents:write", "Write conversations, memories, profiles and pending actions for members")


class AgentError(ServiceError, ValueError):
    pass


@dataclass(frozen=True)
class Owner:
    """The member an agent acts for, inside the token's organization."""

    organization_id: int
    discord_id: str
    token_id: int | None = None


def _save(db, commit: bool) -> None:
    """Commit, or flush when the caller commits several writes as one transaction."""
    if commit:
        db.commit()
    else:
        db.flush()


def _limit(value: object, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise AgentError("limit must be a positive integer")
    return min(value, MAX_LIMIT)


def _text(value: object, name: str, max_len: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentError(f"{name} is required")
    if len(value) > max_len:
        raise AgentError(f"{name} is longer than {max_len} characters")
    return value.strip()


def _confidence(value: object) -> float:
    if value is None:
        return 1.0
    if not isinstance(value, int | float) or isinstance(value, bool) or not 0 <= value <= 1:
        raise AgentError("confidence must be a number from 0 to 1")
    return float(value)


def _conversation_id(value: object) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise AgentError("conversation id must be a UUID") from None


def owner(organization_id: int, discord_id: object, token_id: int | None = None) -> Owner:
    """Validate the member id an agent sent. Discord ids are numeric snowflakes."""
    if not isinstance(discord_id, str) or not discord_id.isdigit() or len(discord_id) > 32:
        raise AgentError("discord_id must be a Discord user id")
    return Owner(organization_id=organization_id, discord_id=discord_id, token_id=token_id)


# Conversations


def _owned(db, who: Owner, conversation_id: str) -> AgentConversation | None:
    return (
        db.query(AgentConversation)
        .filter_by(id=conversation_id, organization_id=who.organization_id, discord_id=who.discord_id)
        .first()
    )


def ensure(
    db, who: Owner, conversation_id: object, channel_id: object, visibility: object, *, commit: bool = True
) -> str:
    """Create the conversation, or confirm the caller already owns it with this channel and visibility.

    An id held by another member, channel or visibility raises AgentError 409. Commits.
    """
    cid = _conversation_id(conversation_id)
    channel = _text(channel_id, "channel_id", 255)
    if visibility not in VISIBILITIES:
        raise AgentError(f"visibility must be one of {', '.join(VISIBILITIES)}")
    row = db.query(AgentConversation).filter_by(id=cid).first()
    if row is None:
        db.add(
            AgentConversation(
                id=cid,
                organization_id=who.organization_id,
                discord_id=who.discord_id,
                channel_id=channel,
                visibility=visibility,
                agent_token_id=who.token_id,
            )
        )
        _save(db, commit)
        return cid
    same = (
        row.organization_id == who.organization_id
        and row.discord_id == who.discord_id
        and row.channel_id == channel
        and row.visibility == visibility
    )
    if not same:
        raise AgentError("Conversation is not owned by this member", 409)
    return cid


def owns(db, who: Owner, conversation_id: object, visibility: object) -> bool:
    cid = _conversation_id(conversation_id)
    row = _owned(db, who, cid)
    return bool(row is not None and row.visibility == visibility)


def load(db, who: Owner, conversation_id: object, limit: object = None) -> list[dict]:
    """The newest summary, then up to limit messages after what it covers, oldest first.

    Each item is {"position", "role", "content"}. A summary's position is the seq it covers.
    An unknown or unowned conversation loads as empty.
    """
    count = _limit(limit, 50)
    cid = _conversation_id(conversation_id)
    if _owned(db, who, cid) is None:
        return []
    summary = (
        db.query(AgentMessage)
        .filter(AgentMessage.conversation_id == cid, AgentMessage.role == "summary")
        .order_by(AgentMessage.seq.desc())
        .first()
    )
    start = 0
    out = []
    if summary is not None:
        start = int(summary.covers_seq or summary.seq)
        out.append({"position": start, "role": "summary", "content": summary.content})
    recent = (
        db.query(AgentMessage)
        .filter(AgentMessage.conversation_id == cid, AgentMessage.role != "summary", AgentMessage.seq > start)
        .order_by(AgentMessage.seq.desc())
        .limit(count)
        .all()
    )
    out.extend({"position": m.seq, "role": m.role, "content": m.content} for m in reversed(recent))
    return out


def _write(
    db, who: Owner, conversation_id: object, rows: list[tuple[str, object, int | None]], commit: bool = True
) -> list[int]:
    cid = _conversation_id(conversation_id)
    conversation = _owned(db, who, cid)
    if conversation is None:
        raise AgentError("Conversation is not owned by this member", 409)
    conversation.updated_at = utcnow()
    messages = [
        AgentMessage(conversation_id=cid, role=role, content=content, covers_seq=covers)
        for role, content, covers in rows
    ]
    db.add_all(messages)
    _save(db, commit)
    return [cast(int, m.seq) for m in messages]


def append(db, who: Owner, conversation_id: object, messages: Any, *, commit: bool = True) -> list[int]:
    """Append messages in one transaction. Each is {"role", "content"}; content is any JSON. Returns their seqs."""
    if not isinstance(messages, list) or not messages:
        raise AgentError("messages must be a non-empty list")
    rows: list[tuple[str, object, int | None]] = []
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in ROLES or "content" not in m:
            raise AgentError(f"each message needs a role ({', '.join(ROLES)}) and content")
        rows.append((m["role"], m["content"], None))
    return _write(db, who, conversation_id, rows, commit)


def append_summary(
    db, who: Owner, conversation_id: object, content: object, covers: object, *, commit: bool = True
) -> int:
    """Store a summary that stands in for every message up to seq covers."""
    if not isinstance(covers, int) or isinstance(covers, bool) or covers < 1:
        raise AgentError("covers must be a message seq")
    if content is None:
        raise AgentError("content is required")
    return _write(db, who, conversation_id, [("summary", content, covers)], commit)[0]


def latest(db, who: Owner, channel_id: object, visibility: object) -> str | None:
    """The member's most recently updated open conversation in a channel."""
    channel = _text(channel_id, "channel_id", 255)
    row = (
        db.query(AgentConversation)
        .filter_by(
            organization_id=who.organization_id,
            discord_id=who.discord_id,
            channel_id=channel,
            visibility=visibility,
            ended_at=None,
        )
        .order_by(AgentConversation.updated_at.desc())
        .first()
    )
    return str(row.id) if row else None


def end(db, who: Owner, channel_id: object) -> int:
    """End the member's open conversations in a channel. Returns how many ended. Commits."""
    channel = _text(channel_id, "channel_id", 255)
    ended = (
        db.query(AgentConversation)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id, channel_id=channel, ended_at=None)
        .update({"ended_at": utcnow()})
    )
    db.commit()
    return int(ended)


def conversation_dict(row: AgentConversation) -> dict:
    return {
        "id": row.id,
        "channel_id": row.channel_id,
        "visibility": row.visibility,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
        "ended_at": iso(row.ended_at),
    }


def list_conversations(db, who: Owner, limit: object = None) -> list[dict]:
    rows = (
        db.query(AgentConversation)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id)
        .order_by(AgentConversation.updated_at.desc())
        .limit(_limit(limit, 100))
        .all()
    )
    return [conversation_dict(row) for row in rows]


def delete_conversation(db, who: Owner, conversation_id: object) -> bool:
    row = _owned(db, who, _conversation_id(conversation_id))
    if row is None:
        return False
    db.query(AgentMessage).filter_by(conversation_id=row.id).delete()
    db.delete(row)
    db.commit()
    return True


# Memories


def _seal(text: str) -> str:
    sealed = secrets.encrypt(text)
    if sealed is None:
        raise AgentError("Sensitive memories need SECRETS_KEY on this server", 503)
    return sealed


def _open(row: AgentMemory) -> str | None:
    if row.sensitivity != "sensitive":
        return str(row.content)
    return secrets.decrypt(str(row.content))


def memory_dict(row: AgentMemory, content: str | None) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "content": content,
        "sensitivity": row.sensitivity,
        "confidence": row.confidence,
        "source_seq": row.source_seq,
        "created_at": iso(row.created_at),
        "expires_at": iso(row.expires_at),
    }


def remember(
    db,
    who: Owner,
    *,
    kind: object,
    content: object,
    sensitivity: object = "normal",
    confidence: object = None,
    source_seq: object = None,
    expires_in_days: object = None,
    commit: bool = True,
) -> dict:
    """Store one memory. Commits unless commit is false."""
    if kind not in MEMORY_KINDS:
        raise AgentError(f"kind must be one of {', '.join(MEMORY_KINDS)}")
    if sensitivity not in SENSITIVITIES:
        raise AgentError(f"sensitivity must be one of {', '.join(SENSITIVITIES)}")
    text = _text(content, "content", 20000)
    if source_seq is not None and (not isinstance(source_seq, int) or isinstance(source_seq, bool)):
        raise AgentError("source_seq must be a message seq")
    if expires_in_days is not None and (not isinstance(expires_in_days, int) or expires_in_days < 1):
        raise AgentError("expires_in_days must be a positive integer")
    row = AgentMemory(
        organization_id=who.organization_id,
        discord_id=who.discord_id,
        kind=kind,
        content=_seal(text) if sensitivity == "sensitive" else text,
        sensitivity=sensitivity,
        confidence=_confidence(confidence),
        source_seq=source_seq,
        agent_token_id=who.token_id,
        expires_at=utcnow() + datetime.timedelta(days=expires_in_days) if expires_in_days else None,
    )
    db.add(row)
    _save(db, commit)
    return memory_dict(row, text)


def recall(db, who: Owner, kinds: object = None, limit: object = None) -> list[dict]:
    """Unexpired memories, most confident first, then newest. Sensitive ones that cannot be decrypted are left out."""
    if kinds is not None and (not isinstance(kinds, list) or any(k not in MEMORY_KINDS for k in kinds)):
        raise AgentError(f"kinds must be a list of {', '.join(MEMORY_KINDS)}")
    query = db.query(AgentMemory).filter(
        AgentMemory.organization_id == who.organization_id,
        AgentMemory.discord_id == who.discord_id,
        or_(AgentMemory.expires_at.is_(None), AgentMemory.expires_at > utcnow()),
    )
    if kinds:
        query = query.filter(AgentMemory.kind.in_(kinds))
    rows = query.order_by(AgentMemory.confidence.desc(), AgentMemory.created_at.desc()).limit(_limit(limit, 20)).all()
    out = []
    for row in rows:
        content = _open(row)
        if content is not None:
            out.append(memory_dict(row, content))
    return out


def forget_memory(db, who: Owner, memory_id: object) -> bool:
    deleted = (
        db.query(AgentMemory)
        .filter_by(id=str(memory_id), organization_id=who.organization_id, discord_id=who.discord_id)
        .delete()
    )
    db.commit()
    return bool(deleted)


# Profile graph


def _entity(value: Any, name: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise AgentError(f"{name} must be an object with kind and label")
    return _text(value.get("kind"), f"{name}.kind", 100), _text(value.get("label"), f"{name}.label", 500)


def _node(db, who: Owner, kind: str, label: str, confidence: float) -> AgentProfileNode:
    node = (
        db.query(AgentProfileNode)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id, kind=kind, label=label)
        .first()
    )
    if node is None:
        node = AgentProfileNode(
            organization_id=who.organization_id,
            discord_id=who.discord_id,
            kind=kind,
            label=label,
            confidence=confidence,
            agent_token_id=who.token_id,
        )
        db.add(node)
        db.flush()
    else:
        node.confidence = max(float(node.confidence), confidence)
        node.updated_at = utcnow()
    return node


def _embed_nodes(nodes: list[AgentProfileNode], embedder: Embedder) -> None:
    """Give nodes without a vector from this model one, from "kind: label". A failure leaves them without."""
    todo = [n for n in nodes if n.embedding is None or n.embedding_model != embedder.model]
    if not todo:
        return
    try:
        vectors = embedder.embed([f"{n.kind}: {n.label}" for n in todo])
    except EmbeddingError:
        logger.warning("profile nodes stored without embeddings count=%s", len(todo))
        return
    if any(len(v) != DIMENSIONS for v in vectors):
        logger.warning("embedding service returned vectors that are not %s long", DIMENSIONS)
        return
    for node, vector in zip(todo, vectors, strict=True):
        node.embedding, node.embedding_model = vector, embedder.model


def upsert(db, who: Owner, facts: Any, *, commit: bool = True, embedder: Embedder | None = None) -> int:
    """Store facts, each {"subject": {kind, label}, "relation", "object": {kind, label}, "confidence"}.

    Existing nodes and edges keep the higher confidence. With an embedder, nodes get vectors for
    similar(). One transaction. Returns how many facts.
    """
    if not isinstance(facts, list):
        raise AgentError("facts must be a list")
    parsed = []
    for fact in facts:
        if not isinstance(fact, dict):
            raise AgentError("each fact must be an object")
        parsed.append(
            (
                _entity(fact.get("subject"), "subject"),
                _text(fact.get("relation"), "relation", 200),
                _entity(fact.get("object"), "object"),
                _confidence(fact.get("confidence")),
            )
        )
    touched: dict[str, AgentProfileNode] = {}
    for (s_kind, s_label), relation, (o_kind, o_label), confidence in parsed:
        subject = _node(db, who, s_kind, s_label, confidence)
        obj = _node(db, who, o_kind, o_label, confidence)
        touched[str(subject.id)], touched[str(obj.id)] = subject, obj
        edge = db.query(AgentProfileEdge).filter_by(from_node=subject.id, to_node=obj.id, relation=relation).first()
        if edge is None:
            db.add(
                AgentProfileEdge(
                    organization_id=who.organization_id,
                    from_node=subject.id,
                    to_node=obj.id,
                    relation=relation,
                    confidence=confidence,
                )
            )
            db.flush()
        else:
            edge.confidence = max(float(edge.confidence), confidence)
    if embedder is not None:
        _embed_nodes(list(touched.values()), embedder)
    _save(db, commit)
    return len(parsed)


def _node_dict(n: AgentProfileNode) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "label": n.label,
        "confidence": n.confidence,
        "created_at": iso(n.created_at),
        "updated_at": iso(n.updated_at),
    }


def profile_nodes(db, who: Owner, limit: object = None) -> list[dict]:
    rows = (
        db.query(AgentProfileNode)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id)
        .order_by(AgentProfileNode.confidence.desc(), AgentProfileNode.updated_at.desc())
        .limit(_limit(limit, 50))
        .all()
    )
    return [_node_dict(n) for n in rows]


_PGVECTOR: dict[str, bool] = {}


def _vector_sql(db) -> bool:
    """Whether the node embedding column is pgvector, so nearest nodes come from SQL."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    url = str(bind.url)
    if url not in _PGVECTOR:
        row = db.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'agent_profile_nodes' AND column_name = 'embedding'"
            )
        ).first()
        _PGVECTOR[url] = row is not None and row[0] == "USER-DEFINED"
    return _PGVECTOR[url]


def similar(db, who: Owner, query: object, limit: object, embedder: Embedder | None) -> list[dict]:
    """The member's profile nodes nearest to the text, nearest first, each with its cosine distance."""
    if embedder is None:
        raise AgentError("Similar nodes need an embedding service (EMBEDDINGS_URL)", 503)
    query_text = _text(query, "text", 2000)
    count = _limit(limit, 10)
    try:
        vector = embedder.embed_query(query_text)
    except EmbeddingError as e:
        raise AgentError("The embedding service failed", 502) from e
    if _vector_sql(db):
        params = {
            "org": who.organization_id,
            "member": who.discord_id,
            "model": embedder.model,
            "vec": Embedding().process_bind_param(vector, None),
            "n": count,
        }
        scored = [
            (float(distance), node_id)
            for node_id, distance in db.execute(
                text(
                    "SELECT id, embedding <=> CAST(:vec AS vector) AS distance FROM agent_profile_nodes"
                    " WHERE organization_id = :org AND discord_id = :member AND embedding IS NOT NULL"
                    " AND embedding_model = :model ORDER BY distance LIMIT :n"
                ),
                params,
            )
        ]
    else:
        rows = db.query(AgentProfileNode.id, AgentProfileNode.embedding).filter(
            AgentProfileNode.organization_id == who.organization_id,
            AgentProfileNode.discord_id == who.discord_id,
            AgentProfileNode.embedding.isnot(None),
            AgentProfileNode.embedding_model == embedder.model,
        )
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        scored = []
        for node_id, embedding in rows:
            other = math.sqrt(sum(x * x for x in embedding)) or 1.0
            scored.append((1.0 - sum(a * b for a, b in zip(vector, embedding, strict=False)) / (norm * other), node_id))
        scored = sorted(scored)[:count]
    nodes = {n.id: n for n in db.query(AgentProfileNode).filter(AgentProfileNode.id.in_([i for _, i in scored]))}
    return [{**_node_dict(nodes[i]), "distance": round(d, 6)} for d, i in scored if i in nodes]


def _relations_query(db, who: Owner):
    from sqlalchemy.orm import aliased

    subject = aliased(AgentProfileNode)
    obj = aliased(AgentProfileNode)
    query = (
        db.query(AgentProfileEdge, subject, obj)
        .join(subject, subject.id == AgentProfileEdge.from_node)
        .join(obj, obj.id == AgentProfileEdge.to_node)
        .filter(
            AgentProfileEdge.organization_id == who.organization_id,
            subject.organization_id == who.organization_id,
            subject.discord_id == who.discord_id,
        )
    )
    return query, subject


def _relation_dict(edge: AgentProfileEdge, subject: AgentProfileNode, obj: AgentProfileNode) -> dict:
    return {
        "subject": {"kind": subject.kind, "label": subject.label},
        "relation": edge.relation,
        "object": {"kind": obj.kind, "label": obj.label},
        "confidence": edge.confidence,
    }


def relations(db, who: Owner, limit: object = None) -> list[dict]:
    query, _ = _relations_query(db, who)
    rows = (
        query.order_by(AgentProfileEdge.confidence.desc(), AgentProfileEdge.created_at.desc())
        .limit(_limit(limit, 50))
        .all()
    )
    return [_relation_dict(*row) for row in rows]


def matching(db, who: Owner, subject_label: object, relation: object) -> list[dict]:
    """Relations from a subject label with a relation name, both compared without case."""
    label = _text(subject_label, "subject", 500)
    name = _text(relation, "relation", 200)
    query, subject = _relations_query(db, who)
    rows = (
        query.filter(func.lower(subject.label) == label.lower(), func.lower(AgentProfileEdge.relation) == name.lower())
        .order_by(AgentProfileEdge.created_at)
        .all()
    )
    return [_relation_dict(*row) for row in rows]


def drop_relation(db, who: Owner, subject_label: object, relation: object, object_label: object) -> bool:
    """Delete one edge, compared without case. Both nodes stay."""
    target = _text(object_label, "object", 500).lower()
    query, subject = _relations_query(db, who)
    label = _text(subject_label, "subject", 500)
    name = _text(relation, "relation", 200)
    rows = query.filter(
        func.lower(subject.label) == label.lower(), func.lower(AgentProfileEdge.relation) == name.lower()
    ).all()
    edges = [edge for edge, _, obj in rows if str(obj.label).lower() == target]
    for edge in edges:
        db.delete(edge)
    db.commit()
    return bool(edges)


def _delete_nodes(db, nodes: list[AgentProfileNode]) -> int:
    ids = [n.id for n in nodes]
    if not ids:
        return 0
    db.query(AgentProfileEdge).filter(
        or_(AgentProfileEdge.from_node.in_(ids), AgentProfileEdge.to_node.in_(ids))
    ).delete(synchronize_session=False)
    db.query(AgentProfileNode).filter(AgentProfileNode.id.in_(ids)).delete(synchronize_session=False)
    return len(ids)


def forget(db, who: Owner, label: object) -> int:
    """Delete every node with this exact label and its edges. Returns nodes deleted. Commits."""
    text = _text(label, "label", 500)
    nodes = (
        db.query(AgentProfileNode)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id, label=text)
        .all()
    )
    count = _delete_nodes(db, nodes)
    db.commit()
    return count


def forget_all(db, who: Owner) -> int:
    """Delete the member's profile graph and memories. Conversations stay. Returns rows deleted. Commits."""
    nodes = db.query(AgentProfileNode).filter_by(organization_id=who.organization_id, discord_id=who.discord_id).all()
    count = _delete_nodes(db, nodes)
    count += db.query(AgentMemory).filter_by(organization_id=who.organization_id, discord_id=who.discord_id).delete()
    db.commit()
    return count


def forget_everything(db, who: Owner) -> int:
    """Delete every conversation, memory and profile row of the member. Returns rows deleted. Commits."""
    ids = [
        row.id
        for row in db.query(AgentConversation.id)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id)
        .all()
    ]
    if ids:
        db.query(AgentMessage).filter(AgentMessage.conversation_id.in_(ids)).delete(synchronize_session=False)
        db.query(AgentConversation).filter(AgentConversation.id.in_(ids)).delete(synchronize_session=False)
    db.query(AgentPendingAction).filter_by(organization_id=who.organization_id, discord_id=who.discord_id).delete()
    return len(ids) + forget_all(db, who)


# Pending actions (confirmations for consequential tool calls)


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
    tid = _conversation_id(token)
    if not isinstance(action, dict):
        raise AgentError("action must be an object")
    digest = _text(payload_hash, "payload_hash", 128)
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
    _save(db, commit)


def claim(db, who: Owner, token: object, approved: object) -> dict | None:
    """Confirm or deny a held action once. Returns {"action", "payload_hash"} or None when it is
    unknown, another member's, expired, or already answered. Commits."""
    if not isinstance(approved, bool):
        raise AgentError("approved must be true or false")
    tid = _conversation_id(token)
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


# Retention


RETENTION_DAYS = int(os.environ.get("AGENT_RETENTION_DAYS", "180"))


def prune(db, now: datetime.datetime | None = None) -> dict:
    """Delete conversations not updated in RETENTION_DAYS, expired memories and old pending actions. Commits."""
    now = now or utcnow()
    cutoff = now - datetime.timedelta(days=RETENTION_DAYS)
    stale = [row.id for row in db.query(AgentConversation.id).filter(AgentConversation.updated_at < cutoff).all()]
    if stale:
        db.query(AgentMessage).filter(AgentMessage.conversation_id.in_(stale)).delete(synchronize_session=False)
        db.query(AgentConversation).filter(AgentConversation.id.in_(stale)).delete(synchronize_session=False)
    memories = db.query(AgentMemory).filter(AgentMemory.expires_at <= now).delete(synchronize_session=False)
    actions = (
        db.query(AgentPendingAction)
        .filter(AgentPendingAction.expires_at < now - datetime.timedelta(days=1))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"conversations": len(stale), "memories": int(memories), "pending_actions": int(actions)}
