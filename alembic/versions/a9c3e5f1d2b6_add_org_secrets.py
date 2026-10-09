"""add org_secrets table

Revision ID: a9c3e5f1d2b6
Revises: f7a2d9c4b1e8
Create Date: 2026-10-08 01:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c3e5f1d2b6"
down_revision: str | Sequence[str] | None = "f7a2d9c4b1e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "org_secrets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_org_secret_name"),
    )
    with op.batch_alter_table("org_secrets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_org_secrets_organization_id"), ["organization_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("org_secrets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_org_secrets_organization_id"))
    op.drop_table("org_secrets")
