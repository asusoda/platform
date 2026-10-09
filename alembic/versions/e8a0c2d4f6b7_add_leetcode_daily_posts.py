"""add leetcode daily posts

Revision ID: e8a0c2d4f6b7
Revises: d6f8b0c2e4a5
Create Date: 2026-10-08 01:45:02.355877

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8a0c2d4f6b7"
down_revision: str | Sequence[str] | None = "d6f8b0c2e4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "leetcode_daily",
        sa.Column("post_date", sa.Date(), nullable=False),
        sa.Column("title_slug", sa.String(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("post_date"),
    )


def downgrade() -> None:
    op.drop_table("leetcode_daily")
