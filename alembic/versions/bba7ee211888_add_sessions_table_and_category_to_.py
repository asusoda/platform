"""add sessions table and category to products

Revision ID: bba7ee211888
Revises: 86f53887ffdc
Create Date: 2026-03-04 17:32:53.365634

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "bba7ee211888"
down_revision: str | Sequence[str] | None = "86f53887ffdc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    This migration is intentionally a no-op because the `sessions` table and
    the `products.category` column are already created in a previous
    migration (`d2ba7436c1b7_initial_schema`). Attempting to recreate them
    would cause errors on a fresh database.
    """
    # No schema changes required.
    pass


def downgrade() -> None:
    """Downgrade schema.

    This migration is a no-op; there are no schema changes to revert here
    because this revision does not apply any.
    """
    # No schema changes to revert.
    pass
