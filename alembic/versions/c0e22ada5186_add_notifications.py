"""add notifications

Revision ID: c0e22ada5186
Revises: 6ca55ae6b9a9
Create Date: 2026-10-09 08:53:15.809366
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0e22ada5186"
down_revision: str | Sequence[str] | None = "6ca55ae6b9a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("event", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("color", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_organization_id", "notifications", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_organization_id", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_table("notifications")
