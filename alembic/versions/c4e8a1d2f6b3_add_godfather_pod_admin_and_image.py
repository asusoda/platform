"""add godfather pod admin and image version

Revision ID: c4e8a1d2f6b3
Revises: b7d3e1f9a2c4
Create Date: 2026-11-04 19:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8a1d2f6b3"
down_revision: str | Sequence[str] | None = "b7d3e1f9a2c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    # Existing pods get no image version, so they show as old until an officer recreates them
    with op.batch_alter_table("compute_pods", schema=None) as batch_op:
        batch_op.add_column(sa.Column("admin_enabled", sa.Boolean(), server_default="false", nullable=False))
        batch_op.add_column(sa.Column("admin_enabled_by", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("admin_enabled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("image_digest", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("image_version", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("compute_pods", schema=None) as batch_op:
        batch_op.drop_column("image_version")
        batch_op.drop_column("image_digest")
        batch_op.drop_column("admin_enabled_at")
        batch_op.drop_column("admin_enabled_by")
        batch_op.drop_column("admin_enabled")
