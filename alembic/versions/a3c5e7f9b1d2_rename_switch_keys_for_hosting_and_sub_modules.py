"""rename the module switches of hosting and the new sub-modules

runpod becomes hosting, leetcode and games become bot.leetcode and bot.games, and storefront becomes points.store.
points.leaderboard and points.checkins take the points value. An org that had the store on and points off gets
points on, with the leaderboard and check-ins off, because a sub-module needs its module on. The old rule holds
for the old keys: a missing key is on. Every org gets every new key, because a missing sub-module key is off.

Revision ID: a3c5e7f9b1d2
Revises: f2a4c6e8b0d1
Create Date: 2026-11-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c5e7f9b1d2"
down_revision: str | Sequence[str] | None = "f2a4c6e8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

# Old key to new key, for the switches that only change their name
RENAMES = {"runpod": "hosting", "leetcode": "bot.leetcode", "games": "bot.games"}

organizations = sa.table("organizations", sa.column("id", sa.Integer), sa.column("config", sa.JSON))


def _on(modules: dict, key: str) -> bool:
    return modules.get(key, True) is not False


def upgrade_switches(modules: dict) -> dict:
    """The new switches for the old ones of one org."""
    found = dict(modules)
    for old, new in RENAMES.items():
        found[new] = _on(found, old)
        found.pop(old, None)
    store = _on(found, "storefront")
    points = _on(found, "points")
    found.pop("storefront", None)
    if store and not points:
        found |= {"points": True, "points.leaderboard": False, "points.checkins": False}
    else:
        found |= {"points.leaderboard": points, "points.checkins": points}
    found["points.store"] = store
    return found


def downgrade_switches(modules: dict) -> dict:
    """The old switches for the new ones of one org."""
    found = dict(modules)
    for old, new in RENAMES.items():
        if new in found:
            found[old] = found.pop(new)
    store = found.pop("points.store", None)
    leaderboard = found.pop("points.leaderboard", None)
    checkins = found.pop("points.checkins", None)
    if store is not None:
        found["storefront"] = store
        # The upgrade turned points on only for the store; turn it off again
        if store and leaderboard is False and checkins is False and found.get("points") is True:
            found["points"] = False
    return found


def _rewrite(change) -> None:
    bind = op.get_bind()
    for org_id, config in bind.execute(sa.select(organizations.c.id, organizations.c.config)).all():
        config = dict(config or {})
        modules = change(dict(config.get("modules") or {}))
        if modules == (config.get("modules") or {}):
            continue
        config["modules"] = modules
        bind.execute(organizations.update().where(organizations.c.id == org_id).values(config=config))


def upgrade() -> None:
    _rewrite(upgrade_switches)


def downgrade() -> None:
    _rewrite(downgrade_switches)
