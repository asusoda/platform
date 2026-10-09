"""add extractor to knowledge sources

Revision ID: b2d4f6a8c0e1
Revises: a0c2e4f6b8d9
Create Date: 2026-10-08 01:16:32.669206

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d4f6a8c0e1"
down_revision: str | Sequence[str] | None = "a0c2e4f6b8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    with op.batch_alter_table("knowledge_sources", schema=None) as batch_op:
        batch_op.add_column(sa.Column("extractor", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("knowledge_sources", schema=None) as batch_op:
        batch_op.drop_column("extractor")
