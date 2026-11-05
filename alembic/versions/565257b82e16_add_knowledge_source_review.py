"""add knowledge source review

Revision ID: 565257b82e16
Revises: d5f9b2e7a1c3
Create Date: 2026-11-05 20:07:25.612482

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "565257b82e16"
down_revision: str | Sequence[str] | None = "d5f9b2e7a1c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.add_column("knowledge_sources", sa.Column("review", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("knowledge_sources") as batch_op:
        batch_op.drop_column("review")
