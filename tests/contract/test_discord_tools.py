"""Discord tools: browse the org's Discord server with the bot token, only inside that server."""

from urllib.parse import parse_qs, urlparse

import pytest

from core.db import db_connect
from core.integrations.discord import DiscordDirectory
from modules.organizations.models import Organization
from tests.contract.test_discord_directory import FakeResponse
from tests.contract.test_officer_tools import _call, _issue, _result

OTHER = "999999"


def _message(id_, channel, text, author="ana", author_id="100501"):
    return {
        "id": str(id_),
        "channel_id": channel,
        "content": text,
        "timestamp": "2026-11-07T10:00:00+00:00",
        "author": {"id": author_id, "username": author},
        "attachments": [],
        "embeds": [],
    }


class Http:
    """Discord REST answers for one server with a category, two channels and a thread."""

    def __init__(self, guild):
        now_id = 1 << 62
        self.guild = guild
        self.channels = [
            {"id": "100010", "type": 4, "name": "Info", "guild_id": guild},
            {
                "id": "100011",
                "type": 0,
                "name": "announcements",
                "parent_id": "100010",
                "guild_id": guild,
                "topic": "News",
            },
            {
                "id": "100012",
                "type": 0,
                "name": "officers",
                "parent_id": "100010",
                "guild_id": guild,
                "permission_overwrites": [{"id": guild, "type": 0, "allow": "0", "deny": str(1 << 10)}],
            },
            {"id": "100020", "type": 2, "name": "Voice", "guild_id": guild},
        ]
        self.messages = {
            "100011": [_message(now_id - i, "100011", f"meeting moved to friday {i}") for i in range(3)],
            "100012": [_message(now_id - 10, "100012", "budget for the hackathon", author="bo", author_id="100502")],
        }

    def get(self, url, headers, timeout):
        parsed = urlparse(url)
        path = parsed.path.split("/api/v10", 1)[1]
        query = parse_qs(parsed.query)
        routes = {
            "/users/@me/guilds": [{"id": self.guild, "name": "SoDA", "icon": None}],
            f"/guilds/{self.guild}/channels": self.channels,
            f"/guilds/{self.guild}/roles": [{"id": "2001", "name": "Officer"}],
            f"/guilds/{self.guild}/threads/active": {
                "threads": [
                    {"id": "100030", "type": 11, "name": "friday plan", "parent_id": "100011", "guild_id": self.guild}
                ]
            },
            "/channels/100011": self.channels[1],
            "/channels/100012": self.channels[2],
            f"/channels/{OTHER}": {"id": OTHER, "type": 0, "guild_id": "123123"},
            "/channels/100011/pins": self.messages["100011"][:1],
            f"/guilds/{self.guild}/members/search": [{"user": {"id": "100501", "username": "ana"}, "roles": ["2001"]}],
        }
        if path.endswith("/messages"):
            channel = path.split("/")[2]
            found = self.messages.get(channel, [])
            if "before" in query:
                found = [m for m in found if int(m["id"]) < int(query["before"][0])]
            return FakeResponse(200, found[: int(query["limit"][0])])
        return FakeResponse(200, routes[path]) if path in routes else FakeResponse(404)


@pytest.fixture
def discord(monkeypatch):
    from modules.users import service as users

    db = db_connect.SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=1).one()
        guild = str(org.guild_id)
    finally:
        db.close()
    http = Http(guild)
    monkeypatch.setattr(users, "bot_directory", lambda: DiscordDirectory("token", http=http))
    return http


def test_discord_tools_need_discord_read(client, discord):
    headers = _issue("members:read")
    assert _call(client, headers, "discord.channels").status_code == 404


def test_server_and_channels(client, discord):
    headers = _issue("discord:read")
    server = _result(client, headers, "discord.server")
    assert server["name"] == "SoDA" and server["channels"] == {"category": 1, "text": 2, "voice": 1}
    listed = _result(client, headers, "discord.channels")
    by_name = {c["name"]: c for c in listed["channels"]}
    assert by_name["announcements"]["category"] == "Info" and by_name["announcements"]["private"] is False
    assert by_name["officers"]["private"] is True
    assert "Info" not in by_name
    assert listed["threads"][0]["name"] == "friday plan"
    assert [c["name"] for c in _result(client, headers, "discord.channels", query="#announce")["channels"]] == [
        "announcements"
    ]


def test_messages_newest_first_with_links(client, discord):
    headers = _issue("discord:read")
    result = _result(client, headers, "discord.messages", channel_id="100011", limit=2, days=7)
    rows = result["messages"]
    assert [r["content"] for r in rows] == ["meeting moved to friday 0", "meeting moved to friday 1"]
    assert rows[0]["url"] == f"https://discord.com/channels/{discord.guild}/100011/{rows[0]['id']}"
    assert result["next_before"] == rows[-1]["id"]
    older = _result(client, headers, "discord.messages", channel_id="100011", before=result["next_before"])
    assert [r["content"] for r in older["messages"]] == ["meeting moved to friday 2"]


def test_a_channel_of_another_server_is_not_found(client, discord):
    headers = _issue("discord:read")
    assert _call(client, headers, "discord.messages", channel_id=OTHER).status_code == 404
    assert _call(client, headers, "discord.pins", channel_id=OTHER).status_code == 404
    assert _call(client, headers, "discord.search", query="x", channel_ids=[OTHER]).status_code == 404


def test_search_reads_every_text_channel(client, discord):
    headers = _issue("discord:read")
    found = _result(client, headers, "discord.search", query="Hackathon budget")
    assert [m["channel_id"] for m in found["matches"]] == ["100012"]
    assert found["scanned"] == 4 and found["channels"] == 2
    by_author = _result(client, headers, "discord.search", query="friday", author_id="100502")
    assert by_author["matches"] == []


def test_pins_and_members(client, discord):
    headers = _issue("discord:read")
    assert len(_result(client, headers, "discord.pins", channel_id="100011")["pins"]) == 1
    members = _result(client, headers, "discord.members", query="an")["members"]
    assert members[0]["username"] == "ana" and members[0]["roles"] == ["2001"]
