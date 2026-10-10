"""add error group context

Revision ID: 70625e187487
Revises: c4d6e8f0a2b4
Create Date: 2026-10-10 06:23:07.554229

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "70625e187487"
down_revision: str | Sequence[str] | None = "c4d6e8f0a2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    with op.batch_alter_table("error_groups", schema=None) as batch_op:
        batch_op.add_column(sa.Column("context", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("error_groups", schema=None) as batch_op:
        batch_op.drop_column("context")
