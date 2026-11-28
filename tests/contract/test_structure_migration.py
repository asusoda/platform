"""The migration that renames the switches of hosting and the new sub-modules, on SQLite and on Postgres.

For every mix of the old switches, each old feature is on after the upgrade exactly when it was on before, and the
downgrade brings back the old switches. Postgres runs when TEST_DATABASE_URL is a Postgres URL, as in CI.
"""

import itertools
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
BEFORE = "f2a4c6e8b0d1"
AFTER = "a3c5e7f9b1d2"
# The switches before this migration. A missing key is on.
OLD_FEATURES = (
    "points",
    "storefront",
    "calendar",
    "games",
    "leetcode",
    "godfather",
    "feeds",
    "uptime",
    "knowledge",
    "integrations",
    "runpod",
)
# The key that gates each old feature after the migration
NEW_KEYS = {"runpod": "hosting", "storefront": "points.store", "leetcode": "bot.leetcode", "games": "bot.games"}
# Every mix of these is tested: missing, on or off
MIXED = ("points", "storefront", "runpod", "leetcode", "games")

organizations = sa.table(
    "organizations",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("prefix", sa.String),
    sa.column("guild_id", sa.String),
    sa.column("is_active", sa.Boolean),
    sa.column("config", sa.JSON),
)


def _configs() -> list[dict | None]:
    found: list[dict | None] = [None, {}, {"theme": "dark"}, {"modules": {"calendar": False, "feeds": True}}]
    for values in itertools.product((None, True, False), repeat=len(MIXED)):
        modules = {key: value for key, value in zip(MIXED, values, strict=True) if value is not None}
        found.append({"modules": modules | {"uptime": False}, "leetcode": {"channel_id": "1"}})
    return found


def _old_on(config: dict | None, feature: str) -> bool:
    return ((config or {}).get("modules") or {}).get(feature, True) is not False


def _alembic(url: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def _postgres_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL") or ""
    return url if url.startswith("postgresql") else None


@pytest.fixture(params=["sqlite", "postgresql"])
def database_url(request, tmp_path):
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'structure.db'}"
        return
    server = _postgres_url()
    if server is None:
        pytest.skip("TEST_DATABASE_URL is not a Postgres URL")
    name = f"structure_{uuid.uuid4().hex[:12]}"
    admin = sa.create_engine(server, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    try:
        yield sa.engine.make_url(server).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _read(url: str) -> dict[int, dict | None]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            return dict(conn.execute(sa.select(organizations.c.id, organizations.c.config)).all())
    finally:
        engine.dispose()


def test_every_old_feature_keeps_its_switch_and_comes_back(database_url):
    from modules.organizations.models import Organization
    from modules.organizations.service import module_enabled

    _alembic(database_url, "upgrade", BEFORE)
    before = dict(enumerate(_configs(), start=1))
    engine = sa.create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(
            organizations.insert(),
            [
                {"id": i, "name": f"Org {i}", "prefix": f"org{i}", "guild_id": str(1000 + i), "is_active": True}
                | {"config": config}
                for i, config in before.items()
            ],
        )
    engine.dispose()

    _alembic(database_url, "upgrade", AFTER)
    after = _read(database_url)
    for org_id, config in before.items():
        org = Organization(config=after[org_id])
        for feature in OLD_FEATURES:
            new = module_enabled(org, NEW_KEYS.get(feature, feature))
            if feature == "points":
                # The leaderboard and check-ins keep the points value. Points stays as it was, except when the
                # store was on with points off: points comes on for the store, with its other parts off.
                assert module_enabled(org, "points.leaderboard") == _old_on(config, "points")
                assert module_enabled(org, "points.checkins") == _old_on(config, "points")
                store_only = _old_on(config, "storefront") and not _old_on(config, "points")
                assert new == (_old_on(config, "points") or store_only), (org_id, config, after[org_id])
            else:
                assert new == _old_on(config, feature), (org_id, feature, config, after[org_id])
        modules = (after[org_id] or {})["modules"]
        assert not set(modules) & {"runpod", "storefront", "leetcode", "games"}
        assert {"bot.leetcode", "bot.games", "points.leaderboard", "points.checkins", "points.store"} <= set(modules)
        # Other config stays
        assert {k: v for k, v in (after[org_id] or {}).items() if k != "modules"} == {
            k: v for k, v in (config or {}).items() if k != "modules"
        }

    _alembic(database_url, "downgrade", BEFORE)
    restored = _read(database_url)
    for org_id, config in before.items():
        for feature in OLD_FEATURES:
            assert _old_on(restored[org_id], feature) == _old_on(config, feature), (org_id, feature, config)
        assert not set((restored[org_id] or {}).get("modules") or {}) & {"hosting", "bot.games", "points.store"}

    _alembic(database_url, "upgrade", AFTER)
    assert _read(database_url) == after
