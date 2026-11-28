"""add points imports, one row for each run of an attendance CSV import

Revision ID: 01b94c83fc0c
Revises: d5f9b2e7a1c3
Create Date: 2026-11-28 08:33:08.414730

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "01b94c83fc0c"
down_revision: str | Sequence[str] | None = "d5f9b2e7a1c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    """Create points_imports and its org index."""
    op.create_table(
        "points_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=255), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=True),
        sa.Column("rows_done", sa.Integer(), nullable=False),
        sa.Column("awarded", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("points_imports", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_points_imports_organization_id"), ["organization_id"], unique=False)


def downgrade() -> None:
    """Drop points_imports."""
    with op.batch_alter_table("points_imports", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_points_imports_organization_id"))

    op.drop_table("points_imports")
