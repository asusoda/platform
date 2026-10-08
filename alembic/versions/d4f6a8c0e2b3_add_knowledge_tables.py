"""add knowledge tables: sources, versions, chunks

Revision ID: d4f6a8c0e2b3
Revises: c8e2f4a6b9d1
Create Date: 2026-10-08 06:00:00.000000

On Postgres with pgvector available, the embedding column becomes vector(1024) with an HNSW index.
Without pgvector it stays text and the vector leg of search runs in Python. Every Postgres gets a
full-text GIN index on the chunk text.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f6a8c0e2b3"
down_revision: str | Sequence[str] | None = "c8e2f4a6b9d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

DIMENSIONS = 1024


def _pgvector_available(bind) -> bool:
    row = bind.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")).first()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    vector = postgres and _pgvector_available(bind)
    if vector:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("public", sa.Boolean(), nullable=False),
        sa.Column("current_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_knowledge_source_key"),
    )
    op.create_table(
        "knowledge_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("knowledge_versions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_knowledge_versions_source_id"), ["source_id"], unique=False)

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("public", sa.Boolean(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("parent_ordinal", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["knowledge_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "ordinal", name="uq_knowledge_chunk_ordinal"),
    )
    with op.batch_alter_table("knowledge_chunks", schema=None) as batch_op:
        batch_op.create_index("ix_knowledge_chunks_scope", ["organization_id", "category", "level"], unique=False)
        batch_op.create_index("ix_knowledge_chunks_public", ["public", "category"], unique=False)

    if vector:
        op.execute(
            f"ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector({DIMENSIONS}) USING embedding::vector"
        )
        op.execute(
            "CREATE INDEX ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks "
            "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )
    if postgres:
        op.execute(
            "CREATE INDEX ix_knowledge_chunks_content_fts ON knowledge_chunks "
            "USING gin (to_tsvector('english', content))"
        )


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    with op.batch_alter_table("knowledge_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_knowledge_versions_source_id"))
    op.drop_table("knowledge_versions")
    op.drop_table("knowledge_sources")
