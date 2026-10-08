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
