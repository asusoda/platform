"""turn off compute, alerts and uptime for existing orgs that do not use them

Revision ID: c4d6e8f0a2b4
Revises: 2eb2a9096622
Create Date: 2026-10-09 22:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d6e8f0a2b4"
down_revision: str | Sequence[str] | None = "2eb2a9096622"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

# Each module and the tables whose rows show that an org uses it.
MODULE_TABLES = {
    "compute": ("compute_pods", "compute_keys"),
    "alerts": ("alert_feeds",),
    "uptime": ("uptime_monitors",),
}

organizations = sa.table("organizations", sa.column("id", sa.Integer), sa.column("config", sa.JSON))


def _orgs_using(bind, tables: tuple[str, ...]) -> set[int]:
    used: set[int] = set()
    for table in tables:
        org_id = sa.table(table, sa.column("organization_id", sa.Integer)).c.organization_id
        used.update(bind.execute(sa.select(org_id).distinct()).scalars())
    return used


def upgrade() -> None:
    # A module missing from an org's config is on. Write false for each module above that the org has no rows for,
    # so an existing org does not get these modules on after the upgrade. An explicit setting stays as it is.
    bind = op.get_bind()
    used = {name: _orgs_using(bind, tables) for name, tables in MODULE_TABLES.items()}
    for org_id, config in bind.execute(sa.select(organizations.c.id, organizations.c.config)).all():
        config = dict(config or {})
        modules = dict(config.get("modules") or {})
        changed = False
        for name in MODULE_TABLES:
            if name not in modules and org_id not in used[name]:
                modules[name] = False
                changed = True
        if changed:
            config["modules"] = modules
            bind.execute(organizations.update().where(organizations.c.id == org_id).values(config=config))


def downgrade() -> None:
    # The upgrade does not record which values it wrote, so the downgrade leaves the switches as they are.
    pass
