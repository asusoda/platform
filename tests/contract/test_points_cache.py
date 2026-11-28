"""Cached officer reads of points: one query per list, ETags, and a fresh list after a write."""

import pytest
from sqlalchemy import event

from tests.contract.conftest import MEMBER_EMAIL

USERS = "/api/points/soda/users"
ENTRIES = "/api/points/soda/get_points"


@pytest.fixture
def queries(app):
    from core.db import db_connect

    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(db_connect.engine, "before_cursor_execute", record)
    yield statements
    event.remove(db_connect.engine, "before_cursor_execute", record)


def test_member_list_does_not_query_each_member(client, officer_headers, queries):
    response = client.get(USERS, headers=officer_headers)
    assert response.status_code == 200
    assert response.get_json()["total_users"] >= 2
    point_sums = [s for s in queries if "sum(points.points)" in s.lower()]
    user_reads = [s for s in queries if s.lstrip().upper().startswith("SELECT") and "FROM users" in s]
    assert len(point_sums) == 1
    assert len(user_reads) <= 2


@pytest.mark.parametrize("path", [USERS, ENTRIES, "/api/points/soda/leaderboard"])
def test_matching_etag_gets_304(client, officer_headers, path):
    first = client.get(path, headers=officer_headers)
    assert first.status_code == 200
    assert first.headers["Cache-Control"] == "private, no-cache"
    etag = first.headers["ETag"]
    again = client.get(path, headers={**officer_headers, "If-None-Match": etag})
    assert again.status_code == 304
    assert again.data == b""


def test_cached_body_matches_jsonify(app, client, officer_headers):
    response = client.get("/api/points/soda/leaderboard", headers=officer_headers)
    with app.app_context():
        from flask import jsonify

        assert response.data == jsonify(response.get_json()).get_data()


def test_cached_read_answers_without_the_database(client, officer_headers, queries):
    assert client.get(ENTRIES, headers=officer_headers).status_code == 200
    queries.clear()
    assert client.get(ENTRIES, headers=officer_headers).status_code == 200
    assert not [s for s in queries if "FROM points" in s]


@pytest.fixture
def remove_cache_check_points(app):
    yield
    from core.db import db_connect
    from modules.points.models import Points

    with db_connect.SessionLocal() as db:
        db.query(Points).filter_by(event="Cache check").delete()
        db.commit()


def test_a_write_drops_the_cached_lists(client, officer_headers, remove_cache_check_points):
    before = client.get(USERS, headers=officer_headers).get_json()
    entries_before = len(client.get(ENTRIES, headers=officer_headers).get_json())
    alice = next(u for u in before["users"] if u["email"] == MEMBER_EMAIL)
    body = {"user_identifier": MEMBER_EMAIL, "points": 3, "event": "Cache check", "awarded_by_officer": "officer"}
    assert client.post("/api/points/soda/assign_points", json=body, headers=officer_headers).status_code < 300
    after = client.get(USERS, headers=officer_headers).get_json()
    assert next(u for u in after["users"] if u["email"] == MEMBER_EMAIL)["points"] == alice["points"] + 3
    assert len(client.get(ENTRIES, headers=officer_headers).get_json()) == entries_before + 1


def test_a_refused_request_is_not_answered_from_the_cache(client, officer_headers):
    assert client.get(USERS, headers=officer_headers).status_code == 200
    assert client.get(USERS).status_code == 401


@pytest.fixture
def notices(monkeypatch):
    """The cache messages that this process sends to the other processes."""
    from core import cache

    sent: list[tuple] = []
    monkeypatch.setattr(cache, "_notify", lambda prefix: sent.append(prefix))
    return sent


def test_a_message_from_another_process_drops_the_cached_lists(client, officer_headers, queries):
    from core import cache

    assert client.get(USERS, headers=officer_headers).status_code == 200
    queries.clear()
    assert cache.apply_message('["org", "soda"]') >= 1
    assert client.get(USERS, headers=officer_headers).status_code == 200
    assert [s for s in queries if "sum(points.points)" in s.lower()]


@pytest.mark.parametrize("payload", ["not json", "{}", "[1, 2]", ""])
def test_a_bad_message_drops_nothing(client, officer_headers, payload):
    from core import cache

    assert client.get(USERS, headers=officer_headers).status_code == 200
    assert cache.apply_message(payload) == 0
    assert cache.cache.get(("org", "soda", "points", "users"))[0]


def test_an_api_write_tells_the_other_processes(client, officer_headers, notices, remove_cache_check_points):
    body = {"user_identifier": MEMBER_EMAIL, "points": 1, "event": "Cache check", "awarded_by_officer": "officer"}
    assert client.post("/api/points/soda/assign_points", json=body, headers=officer_headers).status_code == 201
    assert ("org",) in notices


def test_the_csv_job_tells_the_other_processes(app, notices, remove_cache_check_points):
    from modules.points.submodules.checkins import jobs

    csv_text = f"First Name,Last Name,Email,Checked-In Date\nAlice,A,{MEMBER_EMAIL},2026-10-01\n"
    jobs.import_event_csv(csv_text, "Cache check", 2, "soda")
    assert ("org", "soda") in notices


def test_postgres_notify_reaches_a_listener(app):
    from core import cache
    from core.db import db_connect

    if db_connect.engine.dialect.name != "postgresql":
        pytest.skip("LISTEN/NOTIFY needs Postgres (set TEST_DATABASE_URL)")
    import time

    cache.start_listener()
    cache.cache.set(("org", "soda", "probe"), 1, 60)
    deadline = time.monotonic() + 5
    while cache.cache.get(("org", "soda", "probe"))[0] and time.monotonic() < deadline:
        cache._notify(("org", "soda"))
        time.sleep(0.2)
    assert not cache.cache.get(("org", "soda", "probe"))[0]
