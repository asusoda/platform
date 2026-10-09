"""add webhooks

Revision ID: a1358e0da9ef
Revises: e07a39d0d98f
Create Date: 2026-10-09 04:48:39.418765

Moves each org secret error_webhook_url to a webhook named Errors that sends the errors event. The ciphertext
is copied as it is, so no key is needed. The downgrade copies the first such webhook of each org back.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1358e0da9ef"
down_revision: str | Sequence[str] | None = "e07a39d0d98f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

OLD_SECRET = "error_webhook_url"  # nosec B105 - the name of an org secret, not its value

org_secrets = sa.table(
    "org_secrets",
    sa.column("id", sa.Integer),
    sa.column("organization_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("ciphertext", sa.Text),
    sa.column("updated_at", sa.DateTime),
    sa.column("updated_by", sa.String),
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def upgrade() -> None:
    """Upgrade schema."""
    webhooks = op.create_table(
        "webhooks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("url_ciphertext", sa.Text(), nullable=False),
        sa.Column("url_hint", sa.String(length=100), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_webhook_name"),
    )
    with op.batch_alter_table("webhooks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_webhooks_organization_id"), ["organization_id"], unique=False)

    connection = op.get_bind()
    saved = connection.execute(
        sa.select(org_secrets.c.organization_id, org_secrets.c.ciphertext, org_secrets.c.updated_by).where(
            org_secrets.c.name == OLD_SECRET
        )
    ).all()
    if webhooks is not None and saved:
        op.bulk_insert(
            webhooks,
            [
                {
                    "organization_id": row.organization_id,
                    "name": "Errors",
                    "kind": "discord",
                    "url_ciphertext": row.ciphertext,
                    "url_hint": "discord.com",
                    "events": ["errors"],
                    "enabled": True,
                    "created_at": _now(),
                    "created_by": row.updated_by,
                }
                for row in saved
            ],
        )
        connection.execute(org_secrets.delete().where(org_secrets.c.name == OLD_SECRET))


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()
    webhooks = sa.table(
        "webhooks",
        sa.column("id", sa.Integer),
        sa.column("organization_id", sa.Integer),
        sa.column("kind", sa.String),
        sa.column("url_ciphertext", sa.Text),
        sa.column("events", sa.JSON),
        sa.column("created_by", sa.String),
    )
    restored: dict[int, dict] = {}
    for row in connection.execute(sa.select(webhooks).order_by(webhooks.c.id)).all():
        if row.kind == "discord" and "errors" in (row.events or []) and row.organization_id not in restored:
            restored[row.organization_id] = {
                "organization_id": row.organization_id,
                "name": OLD_SECRET,
                "ciphertext": row.url_ciphertext,
                "updated_at": _now(),
                "updated_by": row.created_by,
            }
    connection.execute(org_secrets.delete().where(org_secrets.c.name == OLD_SECRET))
    if restored:
        op.bulk_insert(org_secrets, list(restored.values()))

    with op.batch_alter_table("webhooks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_webhooks_organization_id"))

    op.drop_table("webhooks")
