"""DiscordDirectory answers officer and member questions from Discord's REST API, with a cache."""

import pytest

from core.integrations.discord import DiscordDirectory, DiscordUnavailable


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self.body = body

    def json(self):
        return self.body


class FakeHttp:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, headers, timeout):
        path = url.split("/api/v10", 1)[1]
        self.calls.append(path)
        assert headers["Authorization"] == "Bot token"
        return self.routes.get(path, FakeResponse(404))


def test_officer_guilds_come_from_member_roles(app):
    http = FakeHttp({"/guilds/1001/members/42": FakeResponse(200, {"roles": ["2001"], "user": {"username": "a"}})})
    directory = DiscordDirectory("token", http=http)
    # Guild 1001 with officer role 2001 matches; guild 1002 returns 404: not a member
    assert directory.officer_guilds("42", [("1001", "2001"), ("1002", "2002")]) == ["1001"]
    assert directory.check_user_membership("42", "1002") is False


def test_lookups_are_cached(app):
    http = FakeHttp({"/guilds/1001/members/42": FakeResponse(200, {"roles": []})})
    directory = DiscordDirectory("token", http=http)
    directory.check_user_membership("42", "1001")
    directory.check_user_membership("42", "1001")
    assert http.calls.count("/guilds/1001/members/42") == 1


def test_discord_errors_raise_unavailable(app):
    directory = DiscordDirectory("token", http=FakeHttp({"/guilds/1001/members/42": FakeResponse(503)}))
    with pytest.raises(DiscordUnavailable):
        directory.check_user_membership("42", "1001")


def test_without_token_it_is_not_ready():
    assert DiscordDirectory(None).is_ready() is False
