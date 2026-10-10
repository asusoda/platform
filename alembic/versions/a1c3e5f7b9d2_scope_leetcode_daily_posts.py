"""scope leetcode daily posts per org

Revision ID: a1c3e5f7b9d2
Revises: e8a0c2d4f6b7
Create Date: 2026-10-08 02:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c3e5f7b9d2"
down_revision: str | Sequence[str] | None = "e8a0c2d4f6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

COLUMNS = "post_date, title_slug, channel_id, message_id, posted_at"


def _create(name: str, scoped: bool) -> None:
    columns = [
        sa.Column("post_date", sa.Date(), nullable=False),
        sa.Column("title_slug", sa.String(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    ]
    if scoped:
        columns.insert(1, sa.Column("scope", sa.String(), server_default="instance", nullable=False))
    op.create_table(name, *columns, sa.PrimaryKeyConstraint(*(("post_date", "scope") if scoped else ("post_date",))))


def upgrade() -> None:
    # The primary key changes, so the table is rebuilt; existing posts become the instance post
    _create("leetcode_daily_new", scoped=True)
    op.execute(
        f"INSERT INTO leetcode_daily_new (scope, {COLUMNS}) SELECT 'instance', {COLUMNS} FROM leetcode_daily"  # nosec B608
    )
    op.drop_table("leetcode_daily")
    op.rename_table("leetcode_daily_new", "leetcode_daily")


def downgrade() -> None:
    _create("leetcode_daily_old", scoped=False)
    op.execute(
        f"INSERT INTO leetcode_daily_old ({COLUMNS}) SELECT {COLUMNS} FROM leetcode_daily WHERE scope = 'instance'"  # nosec B608
    )
    op.drop_table("leetcode_daily")
    op.rename_table("leetcode_daily_old", "leetcode_daily")
