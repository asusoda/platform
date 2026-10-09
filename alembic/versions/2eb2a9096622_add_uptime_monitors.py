"""add uptime monitors

Revision ID: 2eb2a9096622
Revises: dde330bf1668
Create Date: 2026-10-09 21:33:44.997145

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2eb2a9096622"
down_revision: str | Sequence[str] | None = "dde330bf1668"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "uptime_monitors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=500), nullable=False),
        sa.Column("expected_status", sa.String(length=8), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(length=8), nullable=True),
        sa.Column("state_since", sa.DateTime(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_uptime_monitor_name"),
    )
    op.create_table(
        "uptime_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("monitor_id", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("up", sa.Boolean(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["monitor_id"], ["uptime_monitors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("uptime_checks", schema=None) as batch_op:
        batch_op.create_index("ix_uptime_checks_checked_at", ["checked_at"], unique=False)
        batch_op.create_index("ix_uptime_checks_monitor", ["monitor_id", "checked_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("uptime_checks", schema=None) as batch_op:
        batch_op.drop_index("ix_uptime_checks_monitor")
        batch_op.drop_index("ix_uptime_checks_checked_at")

    op.drop_table("uptime_checks")
    op.drop_table("uptime_monitors")
