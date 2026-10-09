"""add embeddings to agent profile nodes

On Postgres with the vector extension installed (the knowledge migration installs it when it is
available), the column becomes vector(1024) with an HNSW index. Otherwise it stays text and
similar nodes are ranked in Python.

Revision ID: c4e6a8b0d2f3
Revises: b2d4f6a8c0e1
Create Date: 2026-10-08 01:26:12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e6a8b0d2f3"
down_revision: str | Sequence[str] | None = "b2d4f6a8c0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

DIMENSIONS = 1024


def _vector_installed(bind) -> bool:
    if bind.dialect.name != "postgresql":
        return False
    return bind.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first() is not None


def upgrade() -> None:
    with op.batch_alter_table("agent_profile_nodes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("embedding", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("embedding_model", sa.String(length=200), nullable=True))
    if _vector_installed(op.get_bind()):
        op.execute(
            f"ALTER TABLE agent_profile_nodes ALTER COLUMN embedding TYPE vector({DIMENSIONS}) USING embedding::vector"
        )
        op.execute(
            "CREATE INDEX ix_agent_profile_nodes_embedding_hnsw ON agent_profile_nodes "
            "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agent_profile_nodes_embedding_hnsw")
    with op.batch_alter_table("agent_profile_nodes", schema=None) as batch_op:
        batch_op.drop_column("embedding_model")
        batch_op.drop_column("embedding")
