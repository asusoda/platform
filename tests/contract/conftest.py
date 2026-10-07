"""Fixtures for the API contract tests: the Flask app, seeded data, and stand-ins for Discord, Clerk and Notion."""

import uuid

import pytest

OFFICER_DISCORD_ID = "900000000000000001"
MEMBER_DISCORD_ID = "900000000000000002"
MEMBER_EMAIL = "alice@asu.edu"

NOTION_PAGE = {
    "id": "notion-page-1",
    "properties": {
        "Name": {"type": "title", "title": [{"plain_text": "Hack Night", "text": {"content": "Hack Night"}}]},
        "Location": {"type": "select", "select": {"name": "BYENG 210"}},
        "Description": {
            "type": "rich_text",
            "rich_text": [{"plain_text": "Bring a laptop", "text": {"content": "Bring a laptop"}}],
        },
        "Date": {"type": "date", "date": {"start": "2026-10-10T18:00:00-07:00", "end": "2026-10-10T20:00:00-07:00"}},
    },
}


class FakeBot:
    """Stands in for the Discord bot: every caller is a member and an officer."""

    def is_ready(self):
        return True

    def check_officer(self, user_id, superadmin_user_id):
        return [1001]

    def check_user_membership(self, user_id, guild_id):
        return True

    def check_user_officer_status(self, user_id, guild_id, role_id):
        return True

    def check_role(self, guild_id, role_id, user_id):
        return True

    def get_guild_roles(self, guild_id):
        return [{"id": "2001", "name": "Officer"}]


def _seed(db_connect):
    from modules.organizations.models import Organization
    from modules.points.models import Points, User, UserOrganizationMembership
    from modules.storefront.models import Order, OrderItem, Product

    db = next(db_connect.get_db())
    try:
        soda = Organization(
            name="SoDA",
            prefix="soda",
            guild_id="1001",
            officer_role_id="2001",
            notion_database_id="notion-db-soda",
            is_active=True,
            config={},
        )
        ais = Organization(name="AI Society", prefix="ais", guild_id="1002", officer_role_id="2002", is_active=True)
        db.add_all([soda, ais])
        db.flush()

        alice = User(
            discord_id=MEMBER_DISCORD_ID,
            username="alice",
            email=MEMBER_EMAIL,
            name="Alice",
            asu_id="1200000001",
            uuid=str(uuid.UUID(int=1)),
        )
        bob = User(username="bob", email="bob@asu.edu", name="Bob", asu_id="1200000002", uuid=str(uuid.UUID(int=2)))
        db.add_all([alice, bob])
        db.flush()

        db.add_all(
            [
                UserOrganizationMembership(user_id=alice.id, organization_id=soda.id),
                UserOrganizationMembership(user_id=bob.id, organization_id=soda.id),
                Points(user_id=alice.id, organization_id=soda.id, points=50, event="GBM", awarded_by_officer="officer"),
                Points(user_id=bob.id, organization_id=soda.id, points=20, event="GBM", awarded_by_officer="officer"),
            ]
        )
        sticker = Product(organization_id=soda.id, name="Sticker", description="Logo sticker", price=5, stock=100)
        db.add(sticker)
        db.flush()
        order = Order(organization_id=soda.id, user_id=alice.id, total_amount=5, status="pending")
        db.add(order)
        db.flush()
        db.add(
            OrderItem(organization_id=soda.id, order_id=order.id, product_id=sticker.id, quantity=1, price_at_time=5)
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session")
def app():
    import main
    from shared import db_connect

    _seed(db_connect)
    setattr(main.app, "auth_bot", FakeBot())  # noqa: B010
    main.app.config["TESTING"] = True
    return main.app


@pytest.fixture(autouse=True)
def stubs(app, monkeypatch):
    """Replace Clerk and Notion with local stand-ins so no test reaches the network."""
    import modules.utils.clerk_auth as clerk_auth

    monkeypatch.setattr(clerk_auth, "verify_clerk_token", lambda token: (MEMBER_EMAIL, {"id": "user_clerk_1"}))
    monkeypatch.setattr(app.multi_org_calendar_service.notion_client, "fetch_events", lambda *a, **k: [NOTION_PAGE])


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def member_client(app):
    """A client whose session holds a Discord login, as after the OAuth callback."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["discord_id"] = MEMBER_DISCORD_ID
    return client


@pytest.fixture(scope="session")
def officer_headers(app):
    from shared import tokenManager

    token = tokenManager.generate_token(username="officer", discord_id=OFFICER_DISCORD_ID)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clerk_headers():
    return {"Authorization": "Bearer clerk-session-token"}
