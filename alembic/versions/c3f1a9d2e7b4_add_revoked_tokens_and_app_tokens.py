"""add revoked_tokens and app_tokens tables

Revision ID: c3f1a9d2e7b4
Revises: a1b2c3d4e5f6
Create Date: 2026-10-07 23:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f1a9d2e7b4"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_revoked_tokens_token_hash"), "revoked_tokens", ["token_hash"], unique=True)
    op.create_table(
        "app_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("app_name", sa.String(length=255), nullable=False),
        sa.Column("discord_id", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_tokens_jti"), "app_tokens", ["jti"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_app_tokens_jti"), table_name="app_tokens")
    op.drop_table("app_tokens")
    op.drop_index(op.f("ix_revoked_tokens_token_hash"), table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
