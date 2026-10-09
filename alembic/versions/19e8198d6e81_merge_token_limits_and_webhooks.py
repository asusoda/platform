"""merge token limits and webhooks

Revision ID: 19e8198d6e81
Revises: 010e740878f3, a1358e0da9ef
Create Date: 2026-10-09 05:28:02.751504

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "19e8198d6e81"
down_revision: str | Sequence[str] | None = ("010e740878f3", "a1358e0da9ef")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    """Join the two heads. No schema change."""


def downgrade() -> None:
    """Split the two heads. No schema change."""
