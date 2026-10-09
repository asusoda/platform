"""DiscordDirectory.search_members turns guild member objects into the rows the dashboard shows."""

from core.integrations.discord import DiscordDirectory


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
        {"id": "1", "name": "Ash", "username": "ash", "avatar": "https://cdn.discordapp.com/avatars/1/abc.png?size=64"},
        {"id": "2", "name": "sam", "username": "sam", "avatar": None},
    ]
