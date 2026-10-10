"""add account grants and logins

Revision ID: e6a8c0d2f4b5
Revises: d4f6a8c0e2b3
Create Date: 2026-10-08 00:56:18.763367

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6a8c0d2f4b5"
down_revision: str | Sequence[str] | None = "d4f6a8c0e2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "account_grants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "discord_id", "provider", name="uq_account_grant_owner"),
    )
    op.create_table(
        "account_logins",
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("state"),
    )
    with op.batch_alter_table("account_logins", schema=None) as batch_op:
        batch_op.create_index("ix_account_logins_expires_at", ["expires_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("account_logins", schema=None) as batch_op:
        batch_op.drop_index("ix_account_logins_expires_at")

    op.drop_table("account_logins")
    op.drop_table("account_grants")
