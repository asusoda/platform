"""add agent tables: conversations, messages, memories, profile graph, pending actions

Revision ID: c8e2f4a6b9d1
Revises: b5d7e9a1c3f2
Create Date: 2026-10-08 04:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8e2f4a6b9d1"
down_revision: str | Sequence[str] | None = "b5d7e9a1c3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=False),
        sa.Column("visibility", sa.String(length=10), nullable=False),
        sa.Column("agent_token_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("agent_conversations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_agent_conversations_owner", ["organization_id", "discord_id", "channel_id", "updated_at"], unique=False
        )

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sensitivity", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_seq", sa.Integer(), nullable=True),
        sa.Column("agent_token_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("agent_memories", schema=None) as batch_op:
        batch_op.create_index("ix_agent_memories_owner", ["organization_id", "discord_id", "kind"], unique=False)

    op.create_table(
        "agent_pending_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("action", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("agent_token_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agent_profile_nodes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("agent_token_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "discord_id", "kind", "label", name="uq_agent_profile_node"),
    )
    with op.batch_alter_table("agent_profile_nodes", schema=None) as batch_op:
        batch_op.create_index("ix_agent_profile_nodes_owner", ["organization_id", "discord_id"], unique=False)

    op.create_table(
        "agent_messages",
        sa.Column("seq", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("covers_seq", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("seq"),
    )
    with op.batch_alter_table("agent_messages", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_agent_messages_conversation_id"), ["conversation_id"], unique=False)

    op.create_table(
        "agent_profile_edges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("from_node", sa.String(length=36), nullable=False),
        sa.Column("to_node", sa.String(length=36), nullable=False),
        sa.Column("relation", sa.String(length=200), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["from_node"], ["agent_profile_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(["to_node"], ["agent_profile_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_node", "to_node", "relation", name="uq_agent_profile_edge"),
    )


def downgrade() -> None:
    op.drop_table("agent_profile_edges")
    with op.batch_alter_table("agent_messages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_messages_conversation_id"))

    op.drop_table("agent_messages")
    with op.batch_alter_table("agent_profile_nodes", schema=None) as batch_op:
        batch_op.drop_index("ix_agent_profile_nodes_owner")

    op.drop_table("agent_profile_nodes")
    op.drop_table("agent_pending_actions")
    with op.batch_alter_table("agent_memories", schema=None) as batch_op:
        batch_op.drop_index("ix_agent_memories_owner")

    op.drop_table("agent_memories")
    with op.batch_alter_table("agent_conversations", schema=None) as batch_op:
        batch_op.drop_index("ix_agent_conversations_owner")

    op.drop_table("agent_conversations")
