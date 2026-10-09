"""add limits to machine tokens

Revision ID: 010e740878f3
Revises: e07a39d0d98f
Create Date: 2026-10-09 04:30:31.292578

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010e740878f3"
down_revision: str | Sequence[str] | None = "e07a39d0d98f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("machine_tokens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("limits", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("machine_tokens", schema=None) as batch_op:
        batch_op.drop_column("limits")
