"""add the deliveries log of every alert message

Revision ID: 9bbb3963c2be
Revises: 01b94c83fc0c
Create Date: 2026-11-28 08:40:26.488251

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9bbb3963c2be"
down_revision: str | Sequence[str] | None = "01b94c83fc0c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("ref", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("channel_id", sa.String(length=32), nullable=True),
        sa.Column("message_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["destination_id"], ["webhooks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("deliveries", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_deliveries_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_deliveries_destination_id"), ["destination_id"], unique=False)
        batch_op.create_index("ix_deliveries_org_created", ["organization_id", "created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("deliveries", schema=None) as batch_op:
        batch_op.drop_index("ix_deliveries_org_created")
        batch_op.drop_index(batch_op.f("ix_deliveries_destination_id"))
        batch_op.drop_index(batch_op.f("ix_deliveries_created_at"))

    op.drop_table("deliveries")
