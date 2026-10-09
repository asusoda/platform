"""add runpod apps and deployments

Revision ID: f8b0d2e4a6c7
Revises: e6a8c0d2f4b5
Create Date: 2026-10-08 01:02:16.785705

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8b0d2e4a6c7"
down_revision: str | Sequence[str] | None = "e6a8c0d2f4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "runpod_apps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=63), nullable=False),
        sa.Column("manifest", sa.Text(), nullable=False),
        sa.Column("pod_id", sa.String(length=64), nullable=True),
        sa.Column("current_tag", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_runpod_app_name"),
    )
    op.create_table(
        "runpod_deployments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("tag", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["app_id"], ["runpod_apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("runpod_deployments", schema=None) as batch_op:
        batch_op.create_index("ix_runpod_deployments_app", ["app_id", "started_at"], unique=False)
        batch_op.create_index("ix_runpod_deployments_status", ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("runpod_deployments", schema=None) as batch_op:
        batch_op.drop_index("ix_runpod_deployments_status")
        batch_op.drop_index("ix_runpod_deployments_app")

    op.drop_table("runpod_deployments")
    op.drop_table("runpod_apps")
