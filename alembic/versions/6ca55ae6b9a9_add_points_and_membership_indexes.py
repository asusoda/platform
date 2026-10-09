"""add points and membership indexes

Revision ID: 6ca55ae6b9a9
Revises: 19e8198d6e81
Create Date: 2026-10-09 07:35:15.733809
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6ca55ae6b9a9"
down_revision: str | Sequence[str] | None = "19e8198d6e81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_index("ix_points_organization_id_user_id", "points", ["organization_id", "user_id"])
    op.create_index("ix_points_user_id", "points", ["user_id"])
    op.create_index(
        "ix_user_organization_memberships_organization_id", "user_organization_memberships", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_user_organization_memberships_organization_id", table_name="user_organization_memberships")
    op.drop_index("ix_points_user_id", table_name="points")
    op.drop_index("ix_points_organization_id_user_id", table_name="points")
