"""The migration that gives each stored Jeopardy game an org, on SQLite and on Postgres.

Postgres runs when TEST_DATABASE_URL is a Postgres URL, as in CI.
"""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
BEFORE = "a3c5e7f9b1d2"
AFTER = "c4e6a8b0d2f4"


def _alembic(url: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture(params=["sqlite", "postgresql"])
def database_url(request, tmp_path):
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'jeopardy.db'}"
        return
    server = os.environ.get("TEST_DATABASE_URL") or ""
    if not server.startswith("postgresql"):
        pytest.skip("TEST_DATABASE_URL is not a Postgres URL")
    name = f"jeopardy_{uuid.uuid4().hex[:12]}"
    admin = sa.create_engine(server, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    try:
        yield sa.engine.make_url(server).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _game(name: str, version: int) -> dict:
    return {"game": {"name": name, "version": version}, "questions": {}}


def _seed(url: str, games_on: dict[int, bool]) -> None:
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        for org_id, on in games_on.items():
            conn.execute(
                sa.text(
                    "INSERT INTO organizations (id, name, prefix, guild_id, is_active, config) "
                    "VALUES (:id, :name, :prefix, :guild, :active, :config)"
                ),
                {
                    "id": org_id,
                    "name": f"Org {org_id}",
                    "prefix": f"org{org_id}",
                    "guild": str(1000 + org_id),
                    "active": True,
                    "config": '{"modules": {"bot.games": %s}}' % ("true" if on else "false"),
                },
            )
        games = sa.table("jeopardy_game", sa.column("id"), sa.column("name"), sa.column("data", sa.JSON))
        conn.execute(
            games.insert(),
            [
                {"id": 1, "name": "Trivia", "data": _game("Trivia", 1)},
                {"id": 2, "name": "Code", "data": _game("Code", 1)},
                {"id": 3, "name": "Trivia", "data": _game("Trivia", 2)},
            ],
        )
        conn.execute(sa.text("INSERT INTO active_game (id, name) VALUES (1, 'Trivia')"))
    engine.dispose()


def _games(url: str) -> list[tuple]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            columns = {c["name"] for c in sa.inspect(conn).get_columns("jeopardy_game")}
            org = "organization_id" if "organization_id" in columns else "NULL"
            rows = conn.execute(sa.text(f"SELECT {org}, name, data FROM jeopardy_game ORDER BY 1, 2")).all()
            found = []
            for org_id, name, data in rows:
                data = data if isinstance(data, dict) else json.loads(data)
                found.append((org_id, name, data["game"]["version"]))
            return found
    finally:
        engine.dispose()


def _active_columns(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT count(*) FROM active_game")).scalar() == 0
            return {c["name"] for c in sa.inspect(conn).get_columns("active_game")}
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("games_on", "owners"),
    [({1: False, 2: True, 3: True}, [2, 3]), ({4: False, 5: False}, [4])],
    ids=["to_each_org_with_games_on", "to_the_lowest_org_when_none_has_games_on"],
)
def test_each_game_goes_to_its_orgs_and_comes_back(database_url, games_on, owners):
    _alembic(database_url, "upgrade", BEFORE)
    _seed(database_url, games_on)

    _alembic(database_url, "upgrade", AFTER)
    # The duplicate Trivia (id 3) is dropped: the old code read the lowest id
    assert _games(database_url) == [(org, name, 1) for org in owners for name in ("Code", "Trivia")]
    assert {"organization_id", "guild_id", "game_data", "helper_data", "updated_at"} <= _active_columns(database_url)

    _alembic(database_url, "downgrade", BEFORE)
    assert _games(database_url) == [(None, "Code", 1), (None, "Trivia", 1)]
    assert _active_columns(database_url) == {"id", "name", "game_data", "helper_data"}
    _alembic(database_url, "upgrade", AFTER)
