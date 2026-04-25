"""add leetcode_link and leetcode_solve tables

Revision ID: a1b2c3d4e5f6
Revises: bba7ee211888
Create Date: 2026-04-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "bba7ee211888"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create leetcode_link and leetcode_solve tables."""
    op.create_table(
        "leetcode_link",
        sa.Column("discord_id", sa.String(), nullable=False),
        sa.Column("leetcode_username", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.PrimaryKeyConstraint("discord_id"),
    )

    op.create_table(
        "leetcode_solve",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("discord_id", sa.String(), nullable=False),
        sa.Column("title_slug", sa.String(), nullable=False),
        sa.Column("solved_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discord_id", "solved_date", name="uq_solve_user_date"),
    )
    op.create_index("ix_leetcode_solve_discord_id", "leetcode_solve", ["discord_id"])
    op.create_index("ix_leetcode_solve_solved_date", "leetcode_solve", ["solved_date"])


def downgrade() -> None:
    """Drop leetcode_link and leetcode_solve tables."""
    op.drop_index("ix_leetcode_solve_solved_date", table_name="leetcode_solve")
    op.drop_index("ix_leetcode_solve_discord_id", table_name="leetcode_solve")
    op.drop_table("leetcode_solve")
    op.drop_table("leetcode_link")
