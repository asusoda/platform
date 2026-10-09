"""add compute connections

Revision ID: 436872ba6583
Revises: c0e22ada5186
Create Date: 2026-10-09 19:52:41.143995

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "436872ba6583"
down_revision: str | Sequence[str] | None = "c0e22ada5186"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "compute_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("pod_id", sa.String(length=64), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("compute_connections", schema=None) as batch_op:
        batch_op.create_index("ix_compute_connections_pod", ["organization_id", "pod_id", "created_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("compute_connections", schema=None) as batch_op:
        batch_op.drop_index("ix_compute_connections_pod")

    op.drop_table("compute_connections")
