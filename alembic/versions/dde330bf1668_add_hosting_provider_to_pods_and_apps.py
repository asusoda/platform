"""add hosting provider to pods and apps

Revision ID: dde330bf1668
Revises: 436872ba6583
Create Date: 2026-10-09 20:05:47.457949

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dde330bf1668"
down_revision: str | Sequence[str] | None = "436872ba6583"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    # The server default gives every existing row the runpod provider
    with op.batch_alter_table("compute_pods", schema=None) as batch_op:
        batch_op.add_column(sa.Column("provider", sa.String(length=32), server_default="runpod", nullable=False))

    with op.batch_alter_table("runpod_apps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("provider", sa.String(length=32), server_default="runpod", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("runpod_apps", schema=None) as batch_op:
        batch_op.drop_column("provider")

    with op.batch_alter_table("compute_pods", schema=None) as batch_op:
        batch_op.drop_column("provider")
