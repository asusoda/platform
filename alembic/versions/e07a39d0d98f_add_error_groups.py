"""add error groups

Revision ID: e07a39d0d98f
Revises: cb77729d70b4
Create Date: 2026-10-09 03:41:06.983504

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e07a39d0d98f"
down_revision: str | Sequence[str] | None = "cb77729d70b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "error_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("org", sa.String(length=100), nullable=True),
        sa.Column("kind", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("route", sa.String(length=255), nullable=True),
        sa.Column("stack", sa.Text(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
    with op.batch_alter_table("error_groups", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_error_groups_last_seen"), ["last_seen"], unique=False)
        batch_op.create_index(batch_op.f("ix_error_groups_org"), ["org"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("error_groups", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_error_groups_org"))
        batch_op.drop_index(batch_op.f("ix_error_groups_last_seen"))

    op.drop_table("error_groups")
