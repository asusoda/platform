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
