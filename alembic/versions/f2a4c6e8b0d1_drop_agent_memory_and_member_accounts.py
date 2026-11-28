"""drop agent memory and member linked accounts

Drops the agent_* and account_* tables, takes the agents and accounts modules out of each org config, deletes
their limit rows, and removes their scopes from tokens and MCP OAuth grants and requests. A machine token left
with no scope is revoked. Downgrade creates the tables again, empty; scopes and data do not come back.

Revision ID: f2a4c6e8b0d1
Revises: 9bbb3963c2be
Create Date: 2026-11-28 09:00:00.000000

"""

import datetime
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a4c6e8b0d1"
down_revision: str | Sequence[str] | None = "9bbb3963c2be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

MODULES = ("agents", "accounts")
SCOPES = frozenset({"agents:read", "agents:write", "accounts:link", "accounts:token"})
LIMITS = ("agents.conversations", "agents.memories")
# Child tables first, so no foreign key points at a dropped table
TABLES = (
    "agent_messages",
    "agent_profile_edges",
    "agent_conversations",
    "agent_profile_nodes",
    "agent_memories",
    "agent_pending_actions",
    "account_logins",
    "account_grants",
)
DIMENSIONS = 1024

organizations = sa.table("organizations", sa.column("id", sa.Integer), sa.column("config", sa.JSON))
machine_tokens = sa.table(
    "machine_tokens", sa.column("id", sa.Integer), sa.column("scopes", sa.JSON), sa.column("revoked_at", sa.DateTime)
)
oauth_grants = sa.table("oauth_grants", sa.column("id", sa.Integer), sa.column("scopes", sa.JSON))
oauth_requests = sa.table(
    "oauth_requests",
    sa.column("id", sa.Integer),
    sa.column("scopes", sa.JSON),
    sa.column("requested_scopes", sa.JSON),
)
org_limits = sa.table("org_limits", sa.column("key", sa.String))
usage_counters = sa.table("usage_counters", sa.column("key", sa.String))


def _strip(scopes) -> list | None:
    """The scopes without the removed ones, or None when nothing changes."""
    if not isinstance(scopes, list):
        return None
    kept = [scope for scope in scopes if scope not in SCOPES]
    return kept if len(kept) != len(scopes) else None


def _strip_column(bind, table, column: str) -> None:
    id_column = table.c.id
    for row_id, scopes in bind.execute(sa.select(id_column, table.c[column])).all():
        kept = _strip(scopes)
        if kept is not None:
            bind.execute(table.update().where(id_column == row_id).values({column: kept}))


def _rewrite_data(bind) -> None:
    for org_id, config in bind.execute(sa.select(organizations.c.id, organizations.c.config)).all():
        if not isinstance(config, dict) or not isinstance(config.get("modules"), dict):
            continue
        modules = {name: on for name, on in config["modules"].items() if name not in MODULES}
        if modules != config["modules"]:
            bind.execute(
                organizations.update().where(organizations.c.id == org_id).values(config={**config, "modules": modules})
            )
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    tokens = sa.select(machine_tokens.c.id, machine_tokens.c.scopes, machine_tokens.c.revoked_at)
    for token_id, scopes, revoked_at in bind.execute(tokens).all():
        kept = _strip(scopes)
        if kept is None:
            continue
        values: dict = {"scopes": kept}
        if not kept and revoked_at is None:
            values["revoked_at"] = now
        bind.execute(machine_tokens.update().where(machine_tokens.c.id == token_id).values(values))
    _strip_column(bind, oauth_grants, "scopes")
    _strip_column(bind, oauth_requests, "scopes")
    _strip_column(bind, oauth_requests, "requested_scopes")
    bind.execute(org_limits.delete().where(org_limits.c.key.in_(LIMITS)))
    bind.execute(usage_counters.delete().where(usage_counters.c.key.in_(LIMITS)))


def upgrade() -> None:
    bind = op.get_bind()
    _rewrite_data(bind)
    op.execute("DROP INDEX IF EXISTS ix_agent_profile_nodes_embedding_hnsw")
    for table in TABLES:
        op.drop_table(table)


def _vector_installed(bind) -> bool:
    if bind.dialect.name != "postgresql":
        return False
    return bind.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first() is not None


def _owner_columns() -> list:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
    ]


def downgrade() -> None:
    op.create_table(
        "agent_conversations",
        *_owner_columns(),
        sa.Column("channel_id", sa.String(length=255), nullable=False),
        sa.Column("visibility", sa.String(length=10), nullable=False),
        sa.Column("agent_token_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_conversations_owner",
        "agent_conversations",
        ["organization_id", "discord_id", "channel_id", "updated_at"],
    )
    op.create_table(
        "agent_memories",
        *_owner_columns(),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sensitivity", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_seq", sa.Integer(), nullable=True),
        sa.Column("agent_token_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_memories_owner", "agent_memories", ["organization_id", "discord_id", "kind"])
    op.create_table(
        "agent_pending_actions",
        *_owner_columns(),
        sa.Column("action", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("agent_token_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agent_profile_nodes",
        *_owner_columns(),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("agent_token_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "discord_id", "kind", "label", name="uq_agent_profile_node"),
    )
    op.create_index("ix_agent_profile_nodes_owner", "agent_profile_nodes", ["organization_id", "discord_id"])
    if _vector_installed(op.get_bind()):
        op.execute(
            f"ALTER TABLE agent_profile_nodes ALTER COLUMN embedding TYPE vector({DIMENSIONS}) USING embedding::vector"
        )
        op.execute(
            "CREATE INDEX ix_agent_profile_nodes_embedding_hnsw ON agent_profile_nodes "
            "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )
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
    op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])
    op.create_table(
        "agent_profile_edges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("from_node", sa.String(length=36), nullable=False),
        sa.Column("to_node", sa.String(length=36), nullable=False),
        sa.Column("relation", sa.String(length=200), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["from_node"], ["agent_profile_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_node"], ["agent_profile_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_node", "to_node", "relation", name="uq_agent_profile_edge"),
    )
    op.create_table(
        "account_grants",
        *_owner_columns(),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "discord_id", "provider", name="uq_account_grant_owner"),
    )
    op.create_table(
        "account_logins",
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("state"),
    )
    op.create_index("ix_account_logins_expires_at", "account_logins", ["expires_at"])
