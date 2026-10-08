"""add procrastinate job queue schema (Postgres only)

Revision ID: e4b8c1f0a7d3
Revises: c3f1a9d2e7b4
Create Date: 2026-10-08 00:40:00.000000

The schema SQL comes from the installed procrastinate package. When procrastinate is upgraded,
add a migration that runs the SQL files from procrastinate's migrations folder
(procrastinate.schema.SchemaManager.get_migrations_path()) for the versions in between.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b8c1f0a7d3"
down_revision: str | Sequence[str] | None = "c3f1a9d2e7b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    from procrastinate.schema import SchemaManager

    op.execute(SchemaManager.get_schema())


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        "DROP TABLE IF EXISTS procrastinate_periodic_defers, procrastinate_events, procrastinate_jobs,"
        " procrastinate_workers CASCADE"
    )
    op.execute(
        "DO $$ DECLARE f regprocedure; BEGIN"
        " FOR f IN SELECT oid::regprocedure FROM pg_proc WHERE proname LIKE 'procrastinate%' LOOP"
        " EXECUTE 'DROP FUNCTION IF EXISTS ' || f || ' CASCADE'; END LOOP; END $$"
    )
    op.execute(
        "DO $$ DECLARE t text; BEGIN"
        " FOR t IN SELECT typname FROM pg_type WHERE typname LIKE 'procrastinate%' AND typtype IN ('c', 'e') LOOP"
        " EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(t) || ' CASCADE'; END LOOP; END $$"
    )
