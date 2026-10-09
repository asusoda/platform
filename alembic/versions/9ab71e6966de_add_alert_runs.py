"""add alert runs

Revision ID: 9ab71e6966de
Revises: b7d9f1a3c5e8
Create Date: 2026-10-08 20:17:39.044669

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9ab71e6966de"
down_revision: str | Sequence[str] | None = "b7d9f1a3c5e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "alert_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("found", sa.Integer(), nullable=True),
        sa.Column("new", sa.Integer(), nullable=True),
        sa.Column("posted", sa.Integer(), nullable=False),
        sa.Column("recorded", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["feed_id"], ["alert_feeds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("alert_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_alert_runs_feed_id"), ["feed_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("alert_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_alert_runs_feed_id"))

    op.drop_table("alert_runs")
