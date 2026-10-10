"""add audit_log table

Revision ID: f7a2d9c4b1e8
Revises: e4b8c1f0a7d3
Create Date: 2026-10-08 01:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a2d9c4b1e8"
down_revision: str | Sequence[str] | None = "e4b8c1f0a7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("org", sa.String(length=100), nullable=True),
        sa.Column("actor_kind", sa.String(length=20), nullable=True),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_log_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_log_org"), ["org"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_log_org"))
        batch_op.drop_index(batch_op.f("ix_audit_log_created_at"))
    op.drop_table("audit_log")
