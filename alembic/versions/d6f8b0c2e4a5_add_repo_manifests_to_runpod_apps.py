"""add repo manifests to runpod apps

Revision ID: d6f8b0c2e4a5
Revises: c4e6a8b0d2f3
Create Date: 2026-10-08 01:29:25.930352

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6f8b0c2e4a5"
down_revision: str | Sequence[str] | None = "c4e6a8b0d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    with op.batch_alter_table("runpod_apps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("repo", sa.String(length=201), nullable=True))
        batch_op.add_column(sa.Column("manifest_path", sa.String(length=200), nullable=True))

    with op.batch_alter_table("runpod_deployments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("manifest", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("manifest_ref", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runpod_deployments", schema=None) as batch_op:
        batch_op.drop_column("manifest_ref")
        batch_op.drop_column("manifest")

    with op.batch_alter_table("runpod_apps", schema=None) as batch_op:
        batch_op.drop_column("manifest_path")
        batch_op.drop_column("repo")
