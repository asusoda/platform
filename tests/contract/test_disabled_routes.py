"""DISABLED_ROUTES: listed path prefixes answer like an unknown route; unset changes nothing."""

import pytest

from core.config import Config, config


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setattr(config, "DISABLED_ROUTES", ("/api/public/getnextevent", "/api/bot/"))


def test_setting_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("DISABLED_ROUTES", " /api/bot/ ,, /api/public/getnextevent ")
    assert Config().DISABLED_ROUTES == ("/api/bot/", "/api/public/getnextevent")
    monkeypatch.delenv("DISABLED_ROUTES")
    assert Config().DISABLED_ROUTES == ()


def test_disabled_routes_answer_like_an_unknown_route(client, disabled):
    unknown = client.get("/api/no-such-route")
    assert unknown.status_code == 404
    for method, path in [
        ("GET", "/api/public/getnextevent"),
        ("GET", "/api/bot/"),
        ("GET", "/api/bot/getavailablegames"),
        ("POST", "/api/bot/uploadgame"),
    ]:
        response = client.open(path, method=method)
        assert response.status_code == 404, path
        assert response.content_type == unknown.content_type
        assert response.data == unknown.data


def test_other_routes_are_unchanged_when_set(client, monkeypatch):
    before = client.get("/api/public/leaderboard")
    monkeypatch.setattr(config, "DISABLED_ROUTES", ("/api/public/getnextevent", "/api/bot/"))
    after = client.get("/api/public/leaderboard")
    assert (after.status_code, after.data) == (before.status_code, before.data)
    assert client.get("/health").status_code == 200


def test_nothing_changes_when_unset(client, monkeypatch):
    monkeypatch.setattr(config, "DISABLED_ROUTES", ())
    response = client.get("/api/bot/")
    assert response.status_code == 200
    assert response.get_json() == {"message": "game api for auth_bot"}
    # The view returns nothing: a 500 in production, an error raised in tests
    with pytest.raises(TypeError):
        client.get("/api/public/getnextevent")
