"""tie Jeopardy games to an org and keep the active game of each org

jeopardy_game gets organization_id. Each stored game goes to each org that has bot.games on, or to the org with the
lowest id when none has. With no org at all, the stored games are deleted. Of games with the same name, the one with
the lowest id stays, as the old code read that one. Then organization_id is not null, with a foreign key and a unique
key on (organization_id, name).

active_game is made again with one row for each org that has a set-up game. No code wrote the old rows.

The downgrade keeps the lowest id of each game name, drops organization_id, and makes the old active_game again,
empty.

Revision ID: c4e6a8b0d2f4
Revises: a3c5e7f9b1d2
Create Date: 2026-11-28 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e6a8b0d2f4"
down_revision: str | Sequence[str] | None = "a3c5e7f9b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

organizations = sa.table("organizations", sa.column("id", sa.Integer), sa.column("config", sa.JSON))
games = sa.table(
    "jeopardy_game",
    sa.column("id", sa.Integer),
    sa.column("organization_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("data", sa.JSON),
)


def _games_on(config: object) -> bool:
    modules = (config or {}).get("modules") if isinstance(config, dict) else None
    return isinstance(modules, dict) and modules.get("bot.games") is True


def _duplicate_ids(rows) -> list[int]:
    """The ids of the rows whose name a row with a lower id has. rows are sorted by id."""
    seen: set = set()
    found = []
    for row in rows:
        if row.name is not None and row.name in seen:
            found.append(row.id)
        seen.add(row.name)
    return found


def upgrade() -> None:
    """Give each stored game an org and make active_game one row for each org."""
    with op.batch_alter_table("jeopardy_game", schema=None) as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))

    conn = op.get_bind()
    orgs = conn.execute(sa.select(organizations.c.id, organizations.c.config).order_by(organizations.c.id)).all()
    targets = [org.id for org in orgs if _games_on(org.config)] or [org.id for org in orgs[:1]]
    rows = conn.execute(sa.select(games.c.id, games.c.name, games.c.data).order_by(games.c.id)).all()
    duplicates = _duplicate_ids(rows)
    if duplicates:
        conn.execute(games.delete().where(games.c.id.in_(duplicates)))
    if not targets:
        conn.execute(games.delete())
    else:
        # Copies take ids after the highest id, so a Postgres sequence that lags (as after a copy from SQLite) is safe
        next_id = max((row.id for row in rows), default=0) + 1
        for row in rows:
            if row.id in duplicates:
                continue
            conn.execute(games.update().where(games.c.id == row.id).values(organization_id=targets[0]))
            for org_id in targets[1:]:
                conn.execute(games.insert().values(id=next_id, organization_id=org_id, name=row.name, data=row.data))
                next_id += 1
        if conn.dialect.name == "postgresql" and rows:
            conn.execute(
                sa.text(
                    "SELECT setval(pg_get_serial_sequence('jeopardy_game', 'id'), (SELECT max(id) FROM jeopardy_game))"
                )
            )

    with op.batch_alter_table("jeopardy_game", schema=None) as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint("uq_jeopardy_game_org_name", ["organization_id", "name"])
        batch_op.create_foreign_key(
            "fk_jeopardy_game_organization_id", "organizations", ["organization_id"], ["id"], ondelete="CASCADE"
        )

    op.drop_table("active_game")
    op.create_table(
        "active_game",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("game_data", sa.JSON(), nullable=False),
        sa.Column("helper_data", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_active_game_organization_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_active_game_organization_id"),
    )


def downgrade() -> None:
    """Keep one stored game for each name, drop organization_id and make the old active_game again."""
    op.drop_table("active_game")
    op.create_table(
        "active_game",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("game_data", sa.JSON(), nullable=True),
        sa.Column("helper_data", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    conn = op.get_bind()
    rows = conn.execute(sa.select(games.c.id, games.c.name).order_by(games.c.id)).all()
    duplicates = _duplicate_ids(rows)
    if duplicates:
        conn.execute(games.delete().where(games.c.id.in_(duplicates)))

    with op.batch_alter_table("jeopardy_game", schema=None) as batch_op:
        batch_op.drop_constraint("fk_jeopardy_game_organization_id", type_="foreignkey")
        batch_op.drop_constraint("uq_jeopardy_game_org_name", type_="unique")
        batch_op.drop_column("organization_id")
