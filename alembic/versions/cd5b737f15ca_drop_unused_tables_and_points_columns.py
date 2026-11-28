"""drop the unused tables sessions, organization_configs and officers, and the org points columns

No code reads or writes these tables or organizations.points_per_message and points_cooldown. The downgrade
makes them again, empty, with the old defaults.

Revision ID: cd5b737f15ca
Revises: c5e7a9b1d3f4
Create Date: 2026-11-28 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd5b737f15ca"
down_revision: str | Sequence[str] | None = "c5e7a9b1d3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("organization_configs")
    op.drop_table("officers")
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.drop_column("points_per_message")
        batch_op.drop_column("points_cooldown")


def downgrade() -> None:
    # Existing orgs get the old model defaults: 1 point for each message and a 60 second cooldown
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("points_per_message", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("points_cooldown", sa.Integer(), nullable=True))
    organizations = sa.table(
        "organizations", sa.column("points_per_message", sa.Integer), sa.column("points_cooldown", sa.Integer)
    )
    op.execute(organizations.update().values(points_per_message=1, points_cooldown=60))
    op.create_table(
        "officers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "organization_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("expiry", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
