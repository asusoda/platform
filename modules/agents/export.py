"""Export of one organization's agent conversations and memories, in pages, for an agent that moves them
to its own store. Sensitive memories are opened; rows that do not open are left out. No Flask here.
"""

from core.log import get_logger
from core.time import iso
from modules.agents import service
from modules.agents.memories import open_content
from modules.agents.models import AgentConversation, AgentMemory, AgentMessage

log = get_logger(__name__)

PAGE = 100


def _message_dict(row: AgentMessage) -> dict:
    return {
        "seq": row.seq,
        "role": row.role,
        "content": row.content,
        "covers_seq": row.covers_seq,
        "created_at": iso(row.created_at),
    }


def conversations_page(db, organization_id: int, after: str | None, limit: object = None) -> dict:
    """Conversations with id greater than after, in id order, each with its messages in seq order.

    Returns {"conversations": [...], "next": the cursor of the next page, or None on the last}.
    """
    count = service.limit(limit, PAGE)
    query = db.query(AgentConversation).filter(AgentConversation.organization_id == organization_id)
    if after:
        query = query.filter(AgentConversation.id > after)
    rows = query.order_by(AgentConversation.id).limit(count).all()
    ids = [row.id for row in rows]
    messages: dict[str, list[dict]] = {cid: [] for cid in ids}
    if ids:
        for m in db.query(AgentMessage).filter(AgentMessage.conversation_id.in_(ids)).order_by(AgentMessage.seq).all():
            messages[m.conversation_id].append(_message_dict(m))
    out = [
        {
            "id": row.id,
            "discord_id": row.discord_id,
            "channel_id": row.channel_id,
            "visibility": row.visibility,
            "created_at": iso(row.created_at),
            "updated_at": iso(row.updated_at),
            "ended_at": iso(row.ended_at),
            "messages": messages[row.id],
        }
        for row in rows
    ]
    return {"conversations": out, "next": ids[-1] if len(ids) == count else None}


def memories_page(db, organization_id: int, after: str | None, limit: object = None) -> dict:
    """Memories with id greater than after, in id order, opened. Returns {"memories": [...], "next": ...}."""
    count = service.limit(limit, PAGE)
    query = db.query(AgentMemory).filter(AgentMemory.organization_id == organization_id)
    if after:
        query = query.filter(AgentMemory.id > after)
    rows = query.order_by(AgentMemory.id).limit(count).all()
    out = []
    for row in rows:
        content = open_content(row)
        if content is None:
            log.warning("agent memory %s does not open; left out of the export", row.id)
            continue
        out.append(
            {
                "id": row.id,
                "discord_id": row.discord_id,
                "kind": row.kind,
                "content": content,
                "sensitivity": row.sensitivity,
                "confidence": row.confidence,
                "created_at": iso(row.created_at),
                "expires_at": iso(row.expires_at),
            }
        )
    return {"memories": out, "next": rows[-1].id if len(rows) == count else None}
