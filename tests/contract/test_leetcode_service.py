"""LeetCode links and solves, through the service the Discord cog uses."""

import datetime

import pytest


@pytest.fixture
def db(app):
    from modules.leetcode.models import LeetCodeLink, LeetCodeSolve
    from shared import db_connect

    session = db_connect.SessionLocal()
    yield session
    session.query(LeetCodeSolve).delete()
    session.query(LeetCodeLink).delete()
    session.commit()
    session.close()


def test_link_solve_and_rank(db):
    from modules.leetcode import service

    service.link(db, "1", "alice_lc")
    service.link(db, "1", "alice_new")
    service.link(db, "2", "bob_lc")
    day = datetime.date(2026, 10, 1)
    service.record_solve(db, "1", "two-sum", day)
    service.record_solve(db, "1", "two-sum", day)  # same day counts once
    service.record_solve(db, "1", "add-two-numbers", day + datetime.timedelta(days=1))
    service.record_solve(db, "2", "two-sum", day)

    assert service.links_for(db, ["1", "2", "3"]) == {"1": "alice_new", "2": "bob_lc"}
    assert service.leaderboard(db) == [("1", "alice_new", 2), ("2", "bob_lc", 1)]
    assert service.stats(db) == {"total_linked": 2, "total_solves": 3, "distinct_solvers": 2}
    assert service.unlink(db, "2") is True
    assert service.unlink(db, "2") is False


QUESTION = {
    "title": "Two Sum",
    "titleSlug": "two-sum",
    "difficulty": "Easy",
    "acRate": 52.3,
    "frontendQuestionId": "1",
    "topicTags": [{"name": "Array"}],
}


@pytest.fixture
def daily_env(db, monkeypatch):
    from modules.leetcode.models import LeetCodeDaily
    from shared import config

    monkeypatch.setattr(config, "LEETCODE_CHANNEL_ID", "555", raising=False)
    monkeypatch.setattr(config, "LEETCODE_ROLE_PING", "777", raising=False)
    monkeypatch.setattr(config, "LEETCODE_DAILY_TIME", "09:00", raising=False)
    monkeypatch.setattr(config, "TIMEZONE", "America/Phoenix", raising=False)
    sent: list = []

    def send(token, channel_id, payload):
        sent.append((str(channel_id), payload))
        return {"id": str(1000 + len(sent))}

    yield sent, send
    db.query(LeetCodeDaily).delete()
    db.commit()


def _at(hour, minute=0, day=8):
    from zoneinfo import ZoneInfo

    return datetime.datetime(2026, 10, day, hour, minute, tzinfo=ZoneInfo("America/Phoenix"))


def test_daily_post_happens_once_after_the_time(db, daily_env):
    from modules.leetcode import daily

    sent, send = daily_env
    reacted: list = []
    react = lambda *a: reacted.append(a)  # noqa: E731
    fetch = lambda: QUESTION  # noqa: E731

    assert daily.post_daily(db, _at(8, 59), fetch, send, react)["reason"] == "not yet"
    assert daily.post_daily(db, _at(9, 0), fetch, send, react)["posted"] is True
    assert daily.post_daily(db, _at(9, 5), fetch, send, react)["reason"] == "already posted"
    assert len(sent) == 1 and reacted[0][2] == "1001"
    channel, payload = sent[0]
    assert channel == "555" and payload["content"] == "<@&777>"
    assert payload["embeds"][0]["url"] == "https://leetcode.com/problems/two-sum/"
    assert payload["embeds"][0]["fields"][3]["value"] == "||`Array`||"
    assert daily.post_daily(db, _at(9, 0, day=9), fetch, send, react)["posted"] is True


def test_a_failed_post_gives_the_day_back(db, daily_env):
    from core.discord_directory import DiscordUnavailable
    from modules.leetcode import daily

    _, send = daily_env

    def down(*args):
        raise DiscordUnavailable("down")

    with pytest.raises(DiscordUnavailable):
        daily.post_daily(db, _at(10), lambda: QUESTION, down, lambda *a: None)
    assert daily.post_daily(db, _at(10, 5), lambda: QUESTION, send, lambda *a: None)["posted"] is True


def test_verify_records_and_announces_each_solve_once(db, daily_env):
    from modules.leetcode import daily, service

    sent, send = daily_env
    daily.post_daily(db, _at(9), lambda: QUESTION, send, lambda *a: None)
    service.link(db, "1", "alice_lc")
    service.link(db, "2", "bob_lc")
    solved_at = int(_at(11).timestamp())
    yesterday = int(_at(11, day=7).timestamp())
    history = {
        "alice_lc": [{"titleSlug": "two-sum", "timestamp": str(solved_at)}],
        "bob_lc": [{"titleSlug": "two-sum", "timestamp": str(yesterday)}],
    }

    result = daily.verify(db, _at(12), lambda name: history[name], send)
    assert result == {"checked": 2, "verified": 1}
    reply = sent[-1][1]
    assert reply["message_reference"]["message_id"] == "1001" and "<@1>" in reply["content"]
    assert daily.verify(db, _at(12, 10), lambda name: history[name], send) == {"checked": 1, "verified": 0}
    assert service.leaderboard(db) == [("1", "alice_lc", 1)]


def test_no_channel_means_no_post(db, daily_env, monkeypatch):
    from modules.leetcode import daily
    from shared import config

    monkeypatch.setattr(config, "LEETCODE_CHANNEL_ID", None, raising=False)
    assert daily.post_daily(db, _at(10), lambda: QUESTION)["posted"] is False
