"""add knowledge runs

Revision ID: cb77729d70b4
Revises: 9ab71e6966de
Create Date: 2026-10-08 20:44:03.248915

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cb77729d70b4"
down_revision: str | Sequence[str] | None = "9ab71e6966de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "knowledge_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("changed", sa.Boolean(), nullable=False),
        sa.Column("chunks", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("knowledge_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_knowledge_runs_organization_id"), ["organization_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("knowledge_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_knowledge_runs_organization_id"))

    op.drop_table("knowledge_runs")
