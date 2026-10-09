"""Officers add the members of the org's Discord server, filtered by role, to the org's members."""

import pytest

from core.integrations.discord import DiscordUnavailable

from .conftest import MEMBER_DISCORD_ID, FakeBot


def _member(id_, name, username, roles=(), bot=False):
    return {"id": id_, "name": name, "username": username, "avatar": None, "roles": list(roles), "bot": bot}


SERVER = [
    _member(MEMBER_DISCORD_ID, "Alice", "alice", ["3001"]),
    _member("900000000000000101", "Dana", "dana", ["3001"]),
    _member("900000000000000102", "Eli", "bob", ["3002"]),  # bob is taken by a user with no Discord id
    _member("900000000000000103", "Helper", "helper", ["3001"], bot=True),
]


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(FakeBot, "list_members", lambda self, guild_id: SERVER, raising=False)


def _soda_members(client, officer_headers):
    """Active SoDA members by Discord id, as {name, username}."""
    from core.db import db_connect
    from modules.users.models import User, UserOrganizationMembership

    db = db_connect.SessionLocal()
    try:
        rows = (
            db.query(User)
            .join(UserOrganizationMembership, UserOrganizationMembership.user_id == User.id)
            .filter(UserOrganizationMembership.organization_id == 1, UserOrganizationMembership.is_active.is_(True))
            .all()
        )
        return {u.discord_id: {"name": u.name, "username": u.username} for u in rows}
    finally:
        db.close()


def test_dry_run_counts_and_changes_nothing(client, officer_headers, server):
    before = _soda_members(client, officer_headers)
    response = client.post("/api/users/soda/discord/sync", json={"dry_run": True}, headers=officer_headers)
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {"matched": 3, "new_users": 2, "joined": 2, "already": 1}
    assert _soda_members(client, officer_headers) == before


def test_sync_by_role_adds_only_holders(client, officer_headers, server):
    body = {"roles": ["3001"]}
    first = client.post("/api/users/soda/discord/sync", json=body, headers=officer_headers).get_json()
    assert first == {"matched": 2, "new_users": 1, "joined": 1, "already": 1}
    members = _soda_members(client, officer_headers)
    assert "900000000000000101" in members
    assert "900000000000000102" not in members
    again = client.post("/api/users/soda/discord/sync", json=body, headers=officer_headers).get_json()
    assert again == {"matched": 2, "new_users": 0, "joined": 0, "already": 2}


def test_sync_leaves_a_taken_username_empty(client, officer_headers, server):
    client.post("/api/users/soda/discord/sync", json={"roles": ["3002"]}, headers=officer_headers)
    eli = _soda_members(client, officer_headers)["900000000000000102"]
    assert eli["name"] == "Eli"
    assert eli["username"] is None


def test_bad_roles_and_missing_intent(client, officer_headers, monkeypatch):
    bad = client.post("/api/users/soda/discord/sync", json={"roles": ["x"]}, headers=officer_headers)
    assert bad.status_code == 400

    def refused(self, guild_id):
        raise DiscordUnavailable("GET /guilds/1001/members returned 403")

    monkeypatch.setattr(FakeBot, "list_members", refused, raising=False)
    response = client.post("/api/users/soda/discord/sync", json={}, headers=officer_headers)
    assert response.status_code == 503
    assert "Server Members Intent" in response.get_json()["error"]


def test_roles_list(client, officer_headers):
    response = client.get("/api/users/soda/discord/roles", headers=officer_headers)
    assert response.status_code == 200
    assert response.get_json() == {"roles": [{"id": "2001", "name": "Officer", "color": "#000000"}]}


def test_sync_needs_an_officer(client):
    assert client.post("/api/users/soda/discord/sync", json={}).status_code == 401
