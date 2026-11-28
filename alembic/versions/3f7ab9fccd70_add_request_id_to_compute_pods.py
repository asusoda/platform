"""add request_id to compute_pods

Revision ID: 3f7ab9fccd70
Revises: c4e6a8b0d2f4
Create Date: 2026-11-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f7ab9fccd70"
down_revision: str | Sequence[str] | None = "c4e6a8b0d2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    # Existing rows keep request_id NULL; the unique key allows many NULLs on SQLite and Postgres
    with op.batch_alter_table("compute_pods", schema=None) as batch_op:
        batch_op.add_column(sa.Column("request_id", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint("uq_compute_pod_request", ["organization_id", "request_id"])


def downgrade() -> None:
    with op.batch_alter_table("compute_pods", schema=None) as batch_op:
        batch_op.drop_constraint("uq_compute_pod_request", type_="unique")
        batch_op.drop_column("request_id")
