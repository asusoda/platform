"""add compute cli codes

Revision ID: b7d3e1f9a2c4
Revises: 2f0c671db898
Create Date: 2026-11-04 17:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d3e1f9a2c4"
down_revision: str | Sequence[str] | None = "2f0c671db898"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "compute_cli_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    with op.batch_alter_table("compute_cli_codes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_compute_cli_codes_expires_at"), ["expires_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("compute_cli_codes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_compute_cli_codes_expires_at"))

    op.drop_table("compute_cli_codes")
