"""add crawl schedule to knowledge sources

Revision ID: a0c2e4f6b8d9
Revises: f8b0d2e4a6c7
Create Date: 2026-10-08 01:09:05.174976

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a0c2e4f6b8d9"
down_revision: str | Sequence[str] | None = "f8b0d2e4a6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    with op.batch_alter_table("knowledge_sources", schema=None) as batch_op:
        batch_op.add_column(sa.Column("fetch_every_hours", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("last_attempt_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_error", sa.Text(), nullable=True))

    with op.batch_alter_table("knowledge_versions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("text_chars", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("knowledge_versions", schema=None) as batch_op:
        batch_op.drop_column("text_chars")

    with op.batch_alter_table("knowledge_sources", schema=None) as batch_op:
        batch_op.drop_column("last_error")
        batch_op.drop_column("last_attempt_at")
        batch_op.drop_column("enabled")
        batch_op.drop_column("fetch_every_hours")
