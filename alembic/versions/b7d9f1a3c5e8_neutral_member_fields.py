"""rename member id and standing columns, add membership profile fields

Revision ID: b7d9f1a3c5e8
Revises: cfdd092e0a0e
Create Date: 2026-10-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d9f1a3c5e8"
down_revision: str | Sequence[str] | None = "cfdd092e0a0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

PROFILE_FIELDS_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _rename(old_id: str, new_id: str, old_standing: str, new_standing: str) -> None:
    # Column renames keep the data in place; no table is rebuilt on either dialect
    op.alter_column("users", old_id, new_column_name=new_id)
    op.alter_column("users", old_standing, new_column_name=new_standing)
    if _postgres():
        op.execute(f"ALTER INDEX ix_users_{old_id} RENAME TO ix_users_{new_id}")
    else:
        op.drop_index(f"ix_users_{old_id}", table_name="users")
        op.create_index(f"ix_users_{new_id}", "users", [new_id], unique=True)


def upgrade() -> None:
    if _postgres():
        op.execute("SET LOCAL lock_timeout = '5s'")
    _rename("asu_id", "student_id", "academic_standing", "class_standing")
    op.add_column(
        "user_organization_memberships",
        sa.Column("profile_fields", PROFILE_FIELDS_TYPE, server_default=sa.text("'{}'"), nullable=False),
    )


def downgrade() -> None:
    if _postgres():
        op.execute("SET LOCAL lock_timeout = '5s'")
    with op.batch_alter_table("user_organization_memberships") as batch_op:
        batch_op.drop_column("profile_fields")
    _rename("student_id", "asu_id", "class_standing", "academic_standing")
