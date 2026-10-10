"""Conversations, messages, memories, the profile graph and pending actions of any agent.

Rows are scoped by organization and the member's Discord id. The columns follow SparkyAI's schema
(apps/scraper/migrations) so its engine can move here without changing its logic. Ids are UUID
strings so they work on SQLite and Postgres alike.
"""

import datetime
import uuid

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from core.base import Base
from modules.knowledge.models import Embedding


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id = Column(String(32), nullable=False)
    channel_id = Column(String(255), nullable=False)
    visibility = Column(String(10), nullable=False, default="public")  # public, private
    agent_token_id = Column(Integer, nullable=True)  # machine token that started it
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now)
    ended_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_agent_conversations_owner", "organization_id", "discord_id", "channel_id", "updated_at"),
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    seq = Column(Integer, primary_key=True, autoincrement=True)  # write order
    conversation_id = Column(
        String(36), ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role = Column(String(10), nullable=False)  # system, user, assistant, tool, summary
    content = Column(JSON, nullable=False)
    covers_seq = Column(Integer, nullable=True)  # a summary stands in for messages up to this seq
    created_at = Column(DateTime, nullable=False, default=_now)


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id = Column(String(32), nullable=False)
    kind = Column(String(20), nullable=False)  # episodic, semantic, profile, task
    content = Column(Text, nullable=False)  # encrypted when sensitivity is sensitive
    sensitivity = Column(String(20), nullable=False, default="normal")
    confidence = Column(Float, nullable=False, default=1.0)
    source_seq = Column(Integer, nullable=True)
    agent_token_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_agent_memories_owner", "organization_id", "discord_id", "kind"),)


class AgentProfileNode(Base):
    __tablename__ = "agent_profile_nodes"

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id = Column(String(32), nullable=False)
    kind = Column(String(100), nullable=False)
    label = Column(String(500), nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    embedding = Column(Embedding(), nullable=True)  # of "kind: label", as Sparky embeds nodes
    embedding_model = Column(String(200), nullable=True)
    agent_token_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("organization_id", "discord_id", "kind", "label", name="uq_agent_profile_node"),
        Index("ix_agent_profile_nodes_owner", "organization_id", "discord_id"),
    )


class AgentProfileEdge(Base):
    __tablename__ = "agent_profile_edges"

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    from_node = Column(String(36), ForeignKey("agent_profile_nodes.id", ondelete="CASCADE"), nullable=False)
    to_node = Column(String(36), ForeignKey("agent_profile_nodes.id", ondelete="CASCADE"), nullable=False)
    relation = Column(String(200), nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (UniqueConstraint("from_node", "to_node", "relation", name="uq_agent_profile_edge"),)


class AgentPendingAction(Base):
    __tablename__ = "agent_pending_actions"

    id = Column(String(36), primary_key=True)  # the confirmation token the agent chose
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id = Column(String(32), nullable=False)
    action = Column(JSON, nullable=False)
    payload_hash = Column(String(128), nullable=False)
    status = Column(String(10), nullable=False, default="pending")  # pending, confirmed, denied, expired
    agent_token_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    expires_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
