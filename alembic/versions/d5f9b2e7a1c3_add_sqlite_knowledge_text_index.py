"""add sqlite knowledge text index

Revision ID: d5f9b2e7a1c3
Revises: c4e8a1d2f6b3
Create Date: 2026-11-05 18:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f9b2e7a1c3"
down_revision: str | Sequence[str] | None = "c4e8a1d2f6b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

TABLE = "knowledge_chunks_fts"
DDL = (
    f"CREATE VIRTUAL TABLE IF NOT EXISTS {TABLE} USING fts5(chunk_id UNINDEXED, content, tokenize='unicode61')",
    f"CREATE TRIGGER IF NOT EXISTS knowledge_chunks_fts_insert AFTER INSERT ON knowledge_chunks BEGIN"
    f" INSERT INTO {TABLE}(rowid, chunk_id, content) VALUES (new.rowid, new.id, new.content); END",
    f"CREATE TRIGGER IF NOT EXISTS knowledge_chunks_fts_delete AFTER DELETE ON knowledge_chunks BEGIN"
    f" DELETE FROM {TABLE} WHERE rowid = old.rowid AND chunk_id = old.id; END",
    f"CREATE TRIGGER IF NOT EXISTS knowledge_chunks_fts_update AFTER UPDATE OF content ON knowledge_chunks BEGIN"
    f" DELETE FROM {TABLE} WHERE rowid = old.rowid AND chunk_id = old.id;"
    f" INSERT INTO {TABLE}(rowid, chunk_id, content) VALUES (new.rowid, new.id, new.content); END",
    f"INSERT INTO {TABLE}(rowid, chunk_id, content) SELECT rowid, id, content FROM knowledge_chunks",
)
DROP = (
    "DROP TRIGGER IF EXISTS knowledge_chunks_fts_update",
    "DROP TRIGGER IF EXISTS knowledge_chunks_fts_delete",
    "DROP TRIGGER IF EXISTS knowledge_chunks_fts_insert",
    f"DROP TABLE IF EXISTS {TABLE}",
)


def upgrade() -> None:
    # SQLite only: Postgres already has a GIN index on the chunk text
    if op.get_bind().dialect.name != "sqlite":
        return
    for statement in DDL:
        op.execute(statement)


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    for statement in DROP:
        op.execute(statement)
