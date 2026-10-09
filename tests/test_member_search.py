"""DiscordDirectory member lookups and the member picker page built from them."""

from core.integrations.discord import DiscordDirectory
from modules.compute.service import member_page
from modules.users.service import discord_roles


class FakeResponse:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


class FakeHttp:
    def __init__(self, body):
        self.body = body
        self.urls: list[str] = []

    def get(self, url, headers=None, timeout=None):
        self.urls.append(url)
        return FakeResponse(self.body)


def test_search_members_names_each_member():
    http = FakeHttp(
        [
            {"nick": "Ash", "user": {"id": "1", "username": "ash", "global_name": "Ash G", "avatar": "abc"}},
            {"nick": None, "user": {"id": "2", "username": "sam", "global_name": None, "avatar": None}},
        ]
    )
    directory = DiscordDirectory("token", http=http)
    members = directory.search_members(42, "a s", 5)
    assert http.urls == ["https://discord.com/api/v10/guilds/42/members/search?query=a+s&limit=5"]
    assert members == [
        {
            "id": "1",
            "name": "Ash",
            "username": "ash",
            "avatar": "https://cdn.discordapp.com/avatars/1/abc.png?size=64",
            "roles": [],
            "bot": False,
        },
        {"id": "2", "name": "sam", "username": "sam", "avatar": None, "roles": [], "bot": False},
    ]


class PagedHttp:
    """Answers the member list in pages of 1000 by the after parameter."""

    def __init__(self, count: int):
        self.count = count
        self.urls: list[str] = []

    def get(self, url, headers=None, timeout=None):
        self.urls.append(url)
        after = int(url.split("after=")[1])
        ids = range(after + 1, min(after + 1000, self.count) + 1)
        return FakeResponse([{"user": {"id": str(i), "username": f"u{i}"}, "roles": []} for i in ids])


def test_list_members_reads_every_page():
    http = PagedHttp(2500)
    members = DiscordDirectory("token", http=http).list_members(42)
    assert len(members) == 2500
    assert len(http.urls) == 3
    assert http.urls[1].endswith("after=1000")


class Directory:
    def __init__(self, members, roles=()):
        self.members = members
        self.roles = list(roles)

    def list_members(self, guild_id):
        return self.members

    def search_members(self, guild_id, query, limit):
        return [m for m in self.members if m["name"].lower().startswith(query.lower())][:limit]

    def get_guild_roles(self, guild_id):
        return self.roles


def _member(id_, name, roles=(), bot=False):
    return {"id": id_, "name": name, "username": name.lower(), "avatar": None, "roles": list(roles), "bot": bot}


def test_member_page_filters_by_role_and_name_and_skips_bots():
    directory = Directory(
        [
            _member("1", "zed", ["10"]),
            _member("2", "Amy", ["10", "11"]),
            _member("3", "bob"),
            _member("4", "Botty", ["10"], bot=True),
        ]
    )
    page = member_page(directory, 42)
    assert [m["name"] for m in page["members"]] == ["Amy", "bob", "zed"]
    assert page["total"] == 3
    assert [m["id"] for m in member_page(directory, 42, role="10")["members"]] == ["2", "1"]
    assert [m["id"] for m in member_page(directory, 42, query="a", role="11")["members"]] == ["2"]
    assert member_page(directory, 42, role="10", limit=1) == {
        "members": [_member("2", "Amy", ["10", "11"])],
        "total": 2,
    }


def test_discord_roles_leave_out_everyone_and_bot_roles():
    roles = [
        {"id": "42", "name": "@everyone", "color": "#000000", "position": 0, "permissions": 0, "managed": False},
        {"id": "10", "name": "Officer", "color": "#ff0000", "position": 5, "permissions": 0, "managed": False},
        {"id": "11", "name": "Member", "color": "#00ff00", "position": 2, "permissions": 0, "managed": False},
        {"id": "12", "name": "Sparky", "color": "#000000", "position": 9, "permissions": 0, "managed": True},
    ]
    assert discord_roles(Directory([], roles), 42) == [
        {"id": "10", "name": "Officer", "color": "#ff0000"},
        {"id": "11", "name": "Member", "color": "#00ff00"},
    ]
