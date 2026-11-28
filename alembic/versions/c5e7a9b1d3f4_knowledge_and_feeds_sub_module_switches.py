"""add the switches of the knowledge and feeds sub-modules, and key the shared content rows by sub-module

Each org gets the new switches from what it uses now. knowledge.asu is on when the org subscribes to asu.
knowledge.web takes the integrations value (a missing key is on), because the web search tool belonged to
integrations. knowledge.asu_signin is on when the org saved an ASU sign-in (the org secret asu_session).
feeds.jobs and feeds.hackathons are on when the org subscribes to careers or has a feed of that kind.

The submodules rows take the sub-module keys: asu becomes knowledge.asu and careers becomes feeds.jobs, with a new
feeds.hackathons row that gets a copy of each careers subscription. The row ids stay, so the shared
knowledge_sources keep their submodule_id. Each org whose new shared switch is on gets its subscription row; the
rows this migration adds have created_by "migration", so the downgrade can take them out again.

Revision ID: c5e7a9b1d3f4
Revises: c4e6a8b0d2f4
Create Date: 2026-11-28 14:00:00.000000

"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5e7a9b1d3f4"
down_revision: str | Sequence[str] | None = "c4e6a8b0d2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

logger = logging.getLogger("alembic.runtime.migration")

NEW_KEYS = ("knowledge.asu", "knowledge.web", "knowledge.asu_signin", "feeds.jobs", "feeds.hackathons")
SHARED = ("knowledge.asu", "feeds.jobs", "feeds.hackathons")
MARK = "migration"
# Old row key to new row key
ROWS = {"asu": "knowledge.asu", "careers": "feeds.jobs"}
# The title and description of each shared row, as the sub-module declares them
TEXTS = {
    "knowledge.asu": (
        "Arizona State University",
        "Public ASU pages and live queries: library hours, events, courses, dining, scholarships, news, shuttles, "
        "jobs, sports.",
    ),
    "feeds.jobs": ("Job alerts", "New software internship and new grad roles from GitHub job lists."),
    "feeds.hackathons": ("Hackathons", "Upcoming hackathons from Hack Club, Euro-Hackathons and Hackalist."),
}
OLD_TEXTS = {
    "asu": TEXTS["knowledge.asu"],
    "careers": (
        "Internships and hackathons",
        "Alert feeds for software internships, new grad roles and upcoming hackathons.",
    ),
}

organizations = sa.table("organizations", sa.column("id", sa.Integer), sa.column("config", sa.JSON))
rows = sa.table(
    "submodules",
    sa.column("id", sa.Integer),
    sa.column("key", sa.String),
    sa.column("title", sa.String),
    sa.column("description", sa.Text),
    sa.column("origin", sa.String),
    sa.column("status", sa.String),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
)
subscriptions = sa.table(
    "submodule_subscriptions",
    sa.column("id", sa.Integer),
    sa.column("organization_id", sa.Integer),
    sa.column("submodule_id", sa.Integer),
    sa.column("created_by", sa.String),
    sa.column("created_at", sa.DateTime),
)
secrets = sa.table("org_secrets", sa.column("organization_id", sa.Integer), sa.column("name", sa.String))
feeds = sa.table("alert_feeds", sa.column("organization_id", sa.Integer), sa.column("kind", sa.String))


def _on(modules: dict, key: str) -> bool:
    return modules.get(key, True) is not False


def new_switches(modules: dict, subscribed: set[str], signed_in: bool, kinds: set[str]) -> dict:
    """The switches of one org after the upgrade. subscribed holds the old row keys (asu, careers) and kinds the
    kinds of the org's feeds."""
    careers = "careers" in subscribed
    return dict(modules) | {
        "knowledge.asu": "asu" in subscribed,
        "knowledge.web": _on(modules, "integrations"),
        "knowledge.asu_signin": signed_in,
        "feeds.jobs": careers or "github_jobs" in kinds,
        "feeds.hackathons": careers or "hackathons" in kinds,
    }


def old_switches(modules: dict) -> dict:
    """The switches of one org after the downgrade."""
    return {key: value for key, value in modules.items() if key not in NEW_KEYS}


def _row_ids(bind) -> dict[str, int]:
    return {str(key): int(row_id) for row_id, key in bind.execute(sa.select(rows.c.id, rows.c.key)).all()}


def _row(bind, key: str) -> int:
    """The id of the row with key, made when missing."""
    found = _row_ids(bind).get(key)
    if found is not None:
        return found
    now = sa.func.now()
    title, description = TEXTS[key]
    bind.execute(
        rows.insert().values(
            key=key,
            title=title,
            description=description,
            origin="code",
            status="shared",
            created_at=now,
            updated_at=now,
        )
    )
    return _row_ids(bind)[key]


def _subscribed(bind) -> dict[int, set[str]]:
    query = sa.select(subscriptions.c.organization_id, rows.c.key).join(rows, rows.c.id == subscriptions.c.submodule_id)
    found: dict[int, set[str]] = {}
    for org_id, key in bind.execute(query).all():
        found.setdefault(int(org_id), set()).add(str(key))
    return found


def _subscribe(bind, org_id: int, row_id: int, created_by: str | None) -> None:
    exists = bind.execute(
        sa.select(subscriptions.c.id).where(
            subscriptions.c.organization_id == org_id, subscriptions.c.submodule_id == row_id
        )
    ).first()
    if exists is None:
        bind.execute(
            subscriptions.insert().values(
                organization_id=org_id, submodule_id=row_id, created_by=created_by, created_at=sa.func.now()
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    subscribed = _subscribed(bind)
    signed_in = {
        int(r[0]) for r in bind.execute(sa.select(secrets.c.organization_id).where(secrets.c.name == "asu_session"))
    }
    kinds: dict[int, set[str]] = {}
    for org_id, kind in bind.execute(sa.select(feeds.c.organization_id, feeds.c.kind)).all():
        kinds.setdefault(int(org_id), set()).add(str(kind))

    switches: dict[int, dict] = {}
    for org_id, config in bind.execute(sa.select(organizations.c.id, organizations.c.config)).all():
        config = dict(config or {})
        modules = dict(config.get("modules") or {})
        found = new_switches(
            modules, subscribed.get(int(org_id), set()), int(org_id) in signed_in, kinds.get(int(org_id), set())
        )
        switches[int(org_id)] = found
        if found.get("integrations", True) is not False and modules.get("knowledge", True) is False:
            # knowledge.web keeps the web search tool through LEGACY_PARENTS in modules/organizations/service.py
            logger.info("org %s has integrations on and knowledge off; knowledge.web follows integrations", org_id)
        config["modules"] = found
        bind.execute(organizations.update().where(organizations.c.id == org_id).values(config=config))

    # The rows take the sub-module keys; their ids stay
    ids = _row_ids(bind)
    for old, new in ROWS.items():
        if old in ids and new not in ids:
            title, description = TEXTS[new]
            bind.execute(
                rows.update().where(rows.c.id == ids[old]).values(key=new, title=title, description=description)
            )
    careers = ids.get("careers")
    if careers is not None:
        hackathons = _row(bind, "feeds.hackathons")
        query = sa.select(subscriptions.c.organization_id, subscriptions.c.created_by).where(
            subscriptions.c.submodule_id == careers
        )
        for org_id, created_by in bind.execute(query).all():
            _subscribe(bind, int(org_id), hackathons, created_by)

    for org_id, found in switches.items():
        for key in SHARED:
            if found[key]:
                _subscribe(bind, org_id, _row(bind, key), MARK)


def downgrade() -> None:
    bind = op.get_bind()
    ids = _row_ids(bind)
    # The copies of the careers subscriptions and the rows this migration added
    bind.execute(subscriptions.delete().where(subscriptions.c.created_by == MARK))
    if "feeds.hackathons" in ids:
        bind.execute(subscriptions.delete().where(subscriptions.c.submodule_id == ids["feeds.hackathons"]))
        bind.execute(rows.delete().where(rows.c.id == ids["feeds.hackathons"]))
    for old, new in ROWS.items():
        if new in ids and old not in ids:
            title, description = OLD_TEXTS[old]
            bind.execute(
                rows.update().where(rows.c.id == ids[new]).values(key=old, title=title, description=description)
            )

    for org_id, config in bind.execute(sa.select(organizations.c.id, organizations.c.config)).all():
        config = dict(config or {})
        modules = old_switches(dict(config.get("modules") or {}))
        if modules == (config.get("modules") or {}):
            continue
        config["modules"] = modules
        bind.execute(organizations.update().where(organizations.c.id == org_id).values(config=config))
