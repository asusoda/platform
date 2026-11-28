"""The migration that adds the knowledge and feeds sub-module switches, on SQLite and on Postgres.

For every mix of the old switches, subscriptions, the ASU sign-in secret and feed kinds, each org can search the
same shared pages, runs the same feeds, has the same web search tool and the same ASU sign-in after the upgrade.
Its feed presets are the same or more: an org with a feed of a kind it did not subscribe to gets that kind's
presets. The downgrade brings back the old rows and switches. Postgres runs when TEST_DATABASE_URL is a Postgres
URL, as in CI.
"""

import datetime
import itertools

import sqlalchemy as sa

from tests.contract.migrations import alembic as _alembic

BEFORE = "c4e6a8b0d2f4"
AFTER = "c5e7a9b1d3f4"
OLD_SWITCHES = ("knowledge", "integrations", "feeds")
KINDS = ("github_jobs", "hackathons")
CAREERS_PRESETS = {"internships", "new-grad", "hackathons"}
KIND_PRESETS = {"github_jobs": {"internships", "new-grad"}, "hackathons": {"hackathons"}}
NOW = datetime.datetime(2026, 11, 28)

organizations = sa.table(
    "organizations",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("prefix", sa.String),
    sa.column("guild_id", sa.String),
    sa.column("is_active", sa.Boolean),
    sa.column("config", sa.JSON),
)
rows = sa.table(
    "submodules",
    sa.column("id", sa.Integer),
    sa.column("key", sa.String),
    sa.column("title", sa.String),
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
secrets = sa.table(
    "org_secrets",
    sa.column("organization_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("ciphertext", sa.Text),
    sa.column("updated_at", sa.DateTime),
)
feeds = sa.table(
    "alert_feeds",
    sa.column("organization_id", sa.Integer),
    sa.column("key", sa.String),
    sa.column("kind", sa.String),
    sa.column("config", sa.JSON),
    sa.column("every_hours", sa.Integer),
    sa.column("enabled", sa.Boolean),
    sa.column("created_at", sa.DateTime),
)
sources = sa.table(
    "knowledge_sources",
    sa.column("id", sa.String),
    sa.column("submodule_id", sa.Integer),
    sa.column("key", sa.String),
    sa.column("category", sa.String),
    sa.column("public", sa.Boolean),
    sa.column("enabled", sa.Boolean),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
)


def _orgs() -> list[dict]:
    """One org for each mix: each old switch missing, on or off; asu and careers subscribed or not; a saved ASU
    sign-in or not; and feeds of no kind, one kind or both."""
    found = []
    kinds = [(), ("github_jobs",), ("hackathons",), KINDS]
    for values in itertools.product((None, True, False), repeat=len(OLD_SWITCHES)):
        modules = {k: v for k, v in zip(OLD_SWITCHES, values, strict=True) if v is not None}
        for asu, careers, signed_in, feed_kinds in itertools.product(
            (False, True), (False, True), (False, True), kinds
        ):
            found.append(
                {"modules": modules, "asu": asu, "careers": careers, "signed_in": signed_in, "kinds": feed_kinds}
            )
    return found


def _old_on(modules: dict, key: str) -> bool:
    return modules.get(key, True) is not False


def _before(org: dict) -> dict:
    """What the org has before the upgrade, by the old rules."""
    modules = org["modules"]
    knowledge, feeds_on = _old_on(modules, "knowledge"), _old_on(modules, "feeds")
    return {
        "search_asu": knowledge and org["asu"],
        "running": dict.fromkeys(org["kinds"], feeds_on),
        "presets": CAREERS_PRESETS if feeds_on and org["careers"] else set(),
        "web_search": _old_on(modules, "integrations"),
        "clubs": knowledge and org["asu"] and org["signed_in"],
    }


def _after(org, subscribed: set[str]) -> dict:
    """What the org has after the upgrade, by the new switches and rows."""
    from modules.feeds.service import KIND_MODULES
    from modules.organizations.service import module_enabled

    def on(key: str) -> bool:
        return module_enabled(org.org, key)

    presets = set()
    if on("feeds.jobs"):
        presets |= KIND_PRESETS["github_jobs"]
    if on("feeds.hackathons"):
        presets |= KIND_PRESETS["hackathons"]
    return {
        "search_asu": on("knowledge") and "knowledge.asu" in subscribed,
        "running": {kind: on(KIND_MODULES[kind]) for kind in org.kinds},
        "presets": presets,
        "web_search": on("knowledge.web"),
        "clubs": on("knowledge.asu") and on("knowledge.asu_signin") and "knowledge.asu" in subscribed and org.signed_in,
    }


class _Org:
    def __init__(self, config: dict | None, kinds: tuple[str, ...], signed_in: bool):
        from modules.organizations.models import Organization

        self.org = Organization(config=config)
        self.kinds = kinds
        self.signed_in = signed_in


def _seed(url: str, orgs: list[dict]) -> int:
    """Insert the orgs, the asu and careers rows with their subscriptions, and one shared asu page. Returns the
    id of the asu row."""
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            organizations.insert(),
            [
                {"id": i, "name": f"Org {i}", "prefix": f"org{i}", "guild_id": str(1000 + i), "is_active": True}
                | {"config": {"modules": org["modules"], "theme": "dark"}}
                for i, org in enumerate(orgs, start=1)
            ],
        )
        conn.execute(
            rows.insert(),
            [
                {"id": 7, "key": "asu", "title": "Arizona State University"}
                | {"origin": "code", "status": "shared", "created_at": NOW, "updated_at": NOW},
                {"id": 9, "key": "careers", "title": "Internships and hackathons"}
                | {"origin": "code", "status": "shared", "created_at": NOW, "updated_at": NOW},
            ],
        )
        subs = [(i, 7) for i, org in enumerate(orgs, start=1) if org["asu"]]
        subs += [(i, 9) for i, org in enumerate(orgs, start=1) if org["careers"]]
        conn.execute(
            subscriptions.insert(),
            [{"organization_id": o, "submodule_id": r, "created_by": "officer", "created_at": NOW} for o, r in subs],
        )
        signed = [i for i, org in enumerate(orgs, start=1) if org["signed_in"]]
        conn.execute(
            secrets.insert(),
            [{"organization_id": i, "name": "asu_session", "ciphertext": "x", "updated_at": NOW} for i in signed],
        )
        made = [(i, kind) for i, org in enumerate(orgs, start=1) for kind in org["kinds"]]
        conn.execute(
            feeds.insert(),
            [
                {"organization_id": i, "key": kind.replace("_", "-"), "kind": kind, "config": {}, "every_hours": 3}
                | {"enabled": True, "created_at": NOW}
                for i, kind in made
            ],
        )
        conn.execute(
            sources.insert().values(id="s1", submodule_id=7, key="asu/library_hours", category="library"),
            {"public": False, "enabled": True, "created_at": NOW, "updated_at": NOW},
        )
    engine.dispose()
    return 7


def _read(url: str) -> tuple[dict[int, dict], dict[int, set[str]], dict[str, int], list[tuple]]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            configs = dict(conn.execute(sa.select(organizations.c.id, organizations.c.config)).all())
            subscribed: dict[int, set[str]] = {}
            query = sa.select(subscriptions.c.organization_id, rows.c.key).join(
                rows, rows.c.id == subscriptions.c.submodule_id
            )
            for org_id, key in conn.execute(query).all():
                subscribed.setdefault(org_id, set()).add(key)
            keys = {key: row_id for row_id, key in conn.execute(sa.select(rows.c.id, rows.c.key)).all()}
            shared = [tuple(r) for r in conn.execute(sa.select(sources.c.key, sources.c.submodule_id)).all()]
            return configs, subscribed, keys, shared
    finally:
        engine.dispose()


def test_every_org_keeps_what_it_searches_runs_and_signs_in_with(database_url):
    _alembic(database_url, "upgrade", BEFORE)
    orgs = _orgs()
    asu_id = _seed(database_url, orgs)
    configs_before, subscribed_before, keys_before, _ = _read(database_url)

    _alembic(database_url, "upgrade", AFTER)
    configs, subscribed, keys, shared = _read(database_url)
    assert keys == {"knowledge.asu": asu_id, "feeds.jobs": 9, "feeds.hackathons": keys["feeds.hackathons"]}
    # The shared page keeps its row
    assert shared == [("asu/library_hours", asu_id)]
    for i, org in enumerate(orgs, start=1):
        before = _before(org)
        after = _after(_Org(configs[i], org["kinds"], org["signed_in"]), subscribed.get(i, set()))
        case = (i, org, configs[i])
        for feature in ("search_asu", "running", "web_search", "clubs"):
            assert after[feature] == before[feature], (feature, *case)
        # Presets are the same, or more for the kinds the org already has feeds of
        assert before["presets"] <= after["presets"], case
        extra = after["presets"] - before["presets"]
        assert extra <= set().union(*(KIND_PRESETS[k] for k in org["kinds"])), case
        # Each shared switch that is on has its subscription row, and the other config stays
        for key in ("knowledge.asu", "feeds.jobs", "feeds.hackathons"):
            assert ((configs[i] or {})["modules"][key] is True) == (key in subscribed.get(i, set())), (key, *case)
        assert configs[i]["theme"] == "dark"

    _alembic(database_url, "downgrade", BEFORE)
    restored, restored_subscribed, restored_keys, shared = _read(database_url)
    assert restored == configs_before
    assert restored_subscribed == subscribed_before
    assert restored_keys == keys_before
    assert shared == [("asu/library_hours", asu_id)]

    _alembic(database_url, "upgrade", AFTER)
    again, again_subscribed, again_keys, _ = _read(database_url)
    assert again == configs and again_subscribed == subscribed
    assert set(again_keys) == set(keys)


def test_an_empty_database_upgrades_and_downgrades(database_url):
    _alembic(database_url, "upgrade", AFTER)
    _alembic(database_url, "downgrade", BEFORE)
    _alembic(database_url, "upgrade", AFTER)
