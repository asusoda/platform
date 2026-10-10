"""add machine_tokens table

Revision ID: b5d7e9a1c3f2
Revises: a9c3e5f1d2b6
Create Date: 2026-10-08 02:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5d7e9a1c3f2"
down_revision: str | Sequence[str] | None = "a9c3e5f1d2b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "machine_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("display", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("machine_tokens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_machine_tokens_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_machine_tokens_token_hash"), ["token_hash"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("machine_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_machine_tokens_token_hash"))
        batch_op.drop_index(batch_op.f("ix_machine_tokens_organization_id"))
    op.drop_table("machine_tokens")
