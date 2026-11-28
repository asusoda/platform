"""Superadmin: adding an org for a Discord server, and the org list."""

from modules.superadmin.service import prefix_for

from .test_access import SUPERADMIN_ID, headers_for


class Guilds:
    def __init__(self, ready=True, guild=None):
        self.ready, self.guild = ready, guild

    def is_ready(self):
        return self.ready

    def get_guild(self, guild_id):
        return self.guild


def test_prefix_follows_the_prefix_rules():
    assert prefix_for("Robotics Club @ ASU!", 1) == "robotics_club_asu"
    assert prefix_for("A" * 40, 1) == "a" * 20
    assert prefix_for("$$", 123456789) == "org_456789"
    assert prefix_for("Admin", 1) == "admin_org"
    assert prefix_for("Store", 1) == "store_org"


def test_a_dashboard_path_cannot_be_an_org_prefix(app):
    import pytest

    from core.db import db_connect
    from modules.organizations import service

    db = db_connect.SessionLocal()
    try:
        with pytest.raises(service.OrganizationError, match="reserved"):
            service.create_organization(db, name="Admin", prefix="admin", guild_id="9911")
    finally:
        db.close()


def test_the_superadmin_gets_in_while_the_bot_is_down(client, monkeypatch, app):
    from core.config import config
    from modules.auth.tokens import token_manager

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    monkeypatch.setattr(app, "discord_directory", Guilds(ready=False))
    assert client.get("/api/superadmin/limits", headers=headers_for(SUPERADMIN_ID)).status_code == 200
    assert client.get("/api/superadmin/limits", headers=headers_for("123")).status_code == 403

    token = token_manager.generate_token(username="u", discord_id=SUPERADMIN_ID)
    with client.session_transaction() as session:
        session["token"] = token
        session["user"] = {"discord_id": SUPERADMIN_ID, "role": "officer"}
    assert client.get("/api/superadmin/limits").status_code == 200
    with client.session_transaction() as session:
        session.clear()


def test_add_org_errors(client, monkeypatch, app):
    from core.config import config

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    headers = headers_for(SUPERADMIN_ID)

    monkeypatch.setattr(app, "discord_directory", Guilds(ready=False))
    assert client.post("/api/superadmin/add_org/77", headers=headers).status_code == 503

    monkeypatch.setattr(app, "discord_directory", Guilds())
    assert client.post("/api/superadmin/add_org/77", headers=headers).status_code == 404

    taken = {"id": "77", "name": "AIS", "icon_url": None}
    monkeypatch.setattr(app, "discord_directory", Guilds(guild=taken))
    assert client.post("/api/superadmin/add_org/77", headers=headers).status_code == 409


def _org_with_data(prefix):
    """An org with members, points, an order, a token, an owned submodule and an app without a pod."""
    import uuid

    from core.db import db_connect
    from core.submodules import SharedContent
    from hosting.models import App, AppDeployment
    from modules.auth import machine_tokens
    from modules.members.models import User, UserOrganizationMembership
    from modules.organizations.models import Organization
    from modules.points.models import Points
    from modules.points.submodules.store.models import Order, OrderItem, Product

    db = db_connect.SessionLocal()
    try:
        org = Organization(name=prefix, prefix=prefix, guild_id=str(uuid.uuid4().int)[:18], is_active=True, config={})
        db.add(org)
        db.flush()
        user = User(username=prefix, email=f"{prefix}@asu.edu", name=prefix, uuid=str(uuid.uuid4()))
        db.add(user)
        db.flush()
        product = Product(organization_id=org.id, name="Shirt", price=5, stock=1)
        order = Order(organization_id=org.id, user_id=user.id, total_amount=5, status="pending")
        app = App(organization_id=org.id, name="bot", manifest="{}")
        db.add_all([product, order, app, UserOrganizationMembership(user_id=user.id, organization_id=org.id)])
        db.add(Points(user_id=user.id, organization_id=org.id, points=5, event="GBM", awarded_by_officer="x"))
        db.add(SharedContent(key=f"{prefix}-pack", title="Pack", owner_org_id=org.id))
        db.flush()
        db.add(OrderItem(organization_id=org.id, order_id=order.id, product_id=product.id, quantity=1, price_at_time=5))
        db.add(AppDeployment(app_id=app.id, tag="v1", status="failed"))
        machine_tokens.issue(db, organization_id=org.id, name="ci", kind="app", scopes=["apps:read"])
        db.commit()
        return org.id, user.id
    finally:
        db.close()


def test_remove_org_deletes_its_rows_and_keeps_shared_ones(client, monkeypatch):
    from core.config import config
    from core.db import db_connect
    from core.submodules import SharedContent
    from modules.members.models import User
    from modules.organizations.models import Organization
    from modules.points.models import Points
    from modules.points.submodules.store.models import Order, OrderItem

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    org_id, user_id = _org_with_data("doomed")
    response = client.delete(f"/api/superadmin/remove_org/{org_id}", headers=headers_for(SUPERADMIN_ID))
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {"message": "Organization doomed removed successfully!"}

    db = db_connect.SessionLocal()
    try:
        assert db.get(Organization, org_id) is None
        for model in (Points, Order, OrderItem):
            assert db.query(model).filter_by(organization_id=org_id).count() == 0
        assert db.get(User, user_id) is not None
        assert db.query(SharedContent).filter_by(key="doomed-pack").one().owner_org_id is None
        assert (
            db.query(Points)
            .filter_by(organization_id=db.query(Organization.id).filter_by(prefix="soda").scalar_subquery())
            .count()
        )
    finally:
        db.close()
    assert client.delete(f"/api/superadmin/remove_org/{org_id}", headers=headers_for(SUPERADMIN_ID)).status_code == 404


def test_remove_org_refuses_while_an_app_has_a_pod(client, monkeypatch):
    from core.config import config
    from core.db import db_connect
    from hosting.models import App

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    org_id, _ = _org_with_data("running")
    db = db_connect.SessionLocal()
    try:
        db.query(App).filter_by(organization_id=org_id).update({"pod_id": "pod1"})
        db.commit()
    finally:
        db.close()
    response = client.delete(f"/api/superadmin/remove_org/{org_id}", headers=headers_for(SUPERADMIN_ID))
    assert response.status_code == 409
    assert "Delete them first" in response.get_json()["error"]


def test_add_org_creates_the_org_with_new_org_modules(client, monkeypatch, app):
    from core.config import config
    from core.db import db_connect
    from modules.organizations.models import Organization
    from modules.organizations.service import new_org_switches

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    guild = {"id": "880088", "name": "Admin", "icon_url": "https://cdn.example/icon.png"}
    monkeypatch.setattr(app, "discord_directory", Guilds(guild=guild))
    response = client.post("/api/superadmin/add_org/880088", headers=headers_for(SUPERADMIN_ID))
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {"message": "Organization Admin added successfully!"}

    db = db_connect.SessionLocal()
    try:
        org = db.query(Organization).filter_by(guild_id="880088").one()
        assert org.prefix == "admin_org"
        assert org.icon_url == guild["icon_url"]
        assert org.config is not None
        assert org.config["modules"] == new_org_switches()
        assert client.post("/api/superadmin/add_org/880088", headers=headers_for(SUPERADMIN_ID)).status_code == 409
        db.delete(org)
        db.commit()
    finally:
        db.close()


def test_org_list_needs_no_bot(client, monkeypatch, app):
    from core.config import config

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    monkeypatch.setattr(app, "discord_directory", Guilds(ready=False))
    response = client.get("/api/superadmin/orgs", headers=headers_for(SUPERADMIN_ID))
    assert response.status_code == 200, response.get_json()
    soda = next(o for o in response.get_json()["orgs"] if o["prefix"] == "soda")
    assert {"members", "modules_on", "near", "open_errors", "last_activity", "officer_role_id"} <= set(soda)
    assert soda["members"] > 0
    assert "config" not in soda
    assert client.get("/api/superadmin/orgs", headers=headers_for("123")).status_code == 403


# The org delete refuses while the org has a pod, so the every-table test leaves this table empty
POD_TABLES = {"compute_pods"}


def _org_fk(column) -> bool:
    return any(fk.column.table.name == "organizations" for fk in column.foreign_keys)


def _value(column, token: str):
    """A value of the column's type for a NOT NULL column: token for text, cut to the column's length."""
    import datetime

    import sqlalchemy as sa

    if isinstance(column.type, sa.Enum):
        return column.type.enums[0]
    if isinstance(column.type, sa.JSON):
        return {}
    if type(column.type).__name__ == "VECTOR":
        return [0.0] * column.type.dim
    python_type = column.type.python_type
    if python_type is str:
        return token[: getattr(column.type, "length", None) or len(token)]
    if python_type is bool:
        return False
    if python_type in (int, float):
        return python_type(1)
    if python_type is datetime.datetime:
        return datetime.datetime(2026, 1, 1)
    if python_type is datetime.date:
        return datetime.date(2026, 1, 1)
    if python_type in (dict, list):
        return python_type()
    if python_type is bytes:
        return token.encode()
    raise AssertionError(f"No test value for {column.table.name}.{column.name} ({column.type})")


def _insert(db, table, org_id: int | None, prefix: str, parents: dict[str, dict]) -> dict:
    """Insert one row and return it. Org FKs get org_id, other FKs the parent row in parents, NOT NULL columns a
    test value."""
    row = {}
    for column in table.columns:
        fks = list(column.foreign_keys)
        if fks and _org_fk(column):
            row[column.name] = org_id
        elif fks:
            parent = fks[0].column.table.name
            if parent in parents:
                row[column.name] = parents[parent][fks[0].column.name]
            elif not column.nullable:
                raise AssertionError(f"{table.name}.{column.name} needs a {parent} row")
        elif column.primary_key and column.autoincrement in (True, "auto") and column.type.python_type is int:
            continue
        elif not column.nullable and column.default is None and column.server_default is None:
            row[column.name] = _value(column, f"{prefix}-{table.name}-{column.name}")
    pk = list(table.primary_key.columns)[0]
    row_id = db.execute(table.insert().values(row)).inserted_primary_key[0]
    return dict(db.execute(table.select().where(pk == row_id)).one()._mapping)


def _fill_every_org_table(db, org_id: int, prefix: str, shared: dict[str, dict]) -> dict[str, dict]:
    """One row in each table that belongs to the org, directly or through a parent row. Returns the rows by table.

    A table with a NOT NULL FK to a table that is not the org's, such as users, gets the row of shared.
    A SET NULL org FK gets a row too: the delete keeps it and clears the FK.
    """
    from core.db import Base

    ids: dict[str, dict] = {}
    for table in Base.metadata.sorted_tables:
        if table.name in POD_TABLES or table.name == "organizations":
            continue
        parents = {fk.column.table.name for fk in table.foreign_keys} - {"organizations"}
        if not any(_org_fk(c) for c in table.columns) and not parents & set(ids):
            continue
        for parent in parents - set(ids) - set(shared):
            parent_table = Base.metadata.tables[parent]
            if parent_table.name in POD_TABLES:
                break
            shared[parent] = _insert(db, parent_table, None, f"shared-{prefix}", {})
        else:
            ids[table.name] = _insert(db, table, org_id, prefix, {**shared, **ids})
    db.commit()
    return ids


def test_remove_org_deletes_a_row_in_every_org_table(client, monkeypatch):
    import uuid

    from sqlalchemy import select

    from core.config import config
    from core.db import Base, db_connect
    from modules.organizations.models import Organization
    from modules.superadmin.service import delete_organization

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    db = db_connect.SessionLocal()
    orgs: dict[str, int] = {}
    shared: dict[str, dict] = {}
    doomed: dict[str, dict] = {}
    kept: dict[str, dict] = {}
    try:
        for prefix in ("every", "keeper"):
            org = Organization(name=prefix, prefix=prefix, guild_id=str(uuid.uuid4().int)[:18], is_active=True)
            db.add(org)
            db.flush()
            orgs[prefix] = int(org.id)
        doomed = _fill_every_org_table(db, orgs["every"], "every", shared)
        kept = _fill_every_org_table(db, orgs["keeper"], "keeper", shared)
        assert set(doomed) == set(kept)
        assert {"points", "orders", "order_items", "machine_tokens", "knowledge_chunks"} <= set(doomed)

        response = client.delete(f"/api/superadmin/remove_org/{orgs['every']}", headers=headers_for(SUPERADMIN_ID))
        assert response.status_code == 200, response.get_json()

        db.expire_all()
        assert db.get(Organization, orgs["every"]) is None
        for name, row in doomed.items():
            table = Base.metadata.tables[name]
            pk = list(table.primary_key.columns)[0]
            row_id = row[pk.name]
            org_columns = [c for c in table.columns if _org_fk(c)]
            if org_columns and all(fk.ondelete == "SET NULL" for c in org_columns for fk in c.foreign_keys):
                left = db.execute(select(*org_columns).where(pk == row_id)).one()
                assert all(value is None for value in left), name
            else:
                assert db.execute(select(pk).where(pk == row_id)).first() is None, name
            assert db.execute(select(pk).where(pk == kept[name][pk.name])).first() is not None, name
    finally:
        db.rollback()
        if "keeper" in orgs and db.get(Organization, orgs["keeper"]) is not None:
            delete_organization(db, orgs["keeper"])
        if "every" in orgs and db.get(Organization, orgs["every"]) is not None:
            delete_organization(db, orgs["every"])
        for table in reversed(Base.metadata.sorted_tables):
            pk = list(table.primary_key.columns)[0]
            ids = [rows[table.name][pk.name] for rows in (doomed, kept, shared) if table.name in rows]
            if ids:
                db.execute(table.delete().where(pk.in_(ids)))
        db.commit()
        db.close()
