"""The search tool: stored pages first, then the live source named, then the web, with parameters read from the query."""

import datetime
import uuid

import pytest

from modules.submodules import find, service
from modules.submodules.fill import dated, fill, named
from modules.submodules.types import QueryError
from submodules.asu.params import code_in, term_for, term_in

TODAY = datetime.date(2026, 11, 5)


def _issue(prefix, *scopes):
    from core.db import db_connect
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(db, organization_id=org_id, name="search", kind="app", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


@pytest.fixture
def writer(app):
    return _issue("soda", "knowledge:read", "knowledge:write")


@pytest.fixture
def live(monkeypatch):
    """Answers every live query with its source and parameters, and records them."""
    asked: list = []

    def answer(db, org_id, org_prefix, name, key, params):
        asked.append((key, params))
        return {"submodule": name, "source": key, "url": f"https://example.edu/{key}", "text": f"live {key}"}

    monkeypatch.setattr(service, "query", answer)
    return asked


def _search(client, headers, **args):
    response = client.post("/api/tools/search", json=args, headers=headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["result"]


def _word():
    return "w" + uuid.uuid4().hex[:10]


def test_a_course_code_is_read_however_the_query_spaces_it():
    assert code_in("does cse310 have seats") == "CSE 310"
    assert code_in("CSE 310 open seats") == "CSE 310"
    assert code_in("prereqs for mat 243?") == "MAT 243"
    assert code_in("what are the prerequisites") is None
    assert code_in("is 310 open") is None


def test_the_term_comes_from_the_query_or_the_calendar():
    assert term_in("CSE 310 fall 2026") == "Fall 2026"
    assert term_in("spring, 2027 classes") == "Spring 2027"
    assert term_for(datetime.date(2026, 3, 1)) == "Spring 2026"
    assert term_for(datetime.date(2026, 6, 1)) == "Summer 2026"
    assert term_for(TODAY) == "Fall 2026"


def test_a_class_search_takes_the_code_term_and_open_only_from_the_query():
    _, courses = find.SOURCES["courses"]
    assert fill(courses, "does CSE 310 have open seats spring 2027", TODAY) == {
        "keywords": "CSE 310",
        "term": "Spring 2027",
        "open_only": "true",
    }
    params = fill(courses, "machine learning classes on monday", TODAY)
    assert params == {"keywords": "machine learning on monday", "days": "monday", "term": "Fall 2026"}
    assert "session" not in fill(courses, "is there a section of CSE 310", TODAY), "a one-letter choice is not read"


def test_a_query_missing_a_required_choice_is_refused_with_the_choices():
    _, dining = find.SOURCES["dining"]
    with pytest.raises(QueryError, match="campus") as refused:
        fill(dining, "dining hours today", TODAY)
    assert "tempe" in str(refused.value).lower()
    assert fill(dining, "tempe dining hours", TODAY)["campus"].lower() == "tempe"


def test_a_required_date_defaults_to_today_and_a_named_one_is_kept():
    _, rooms = find.SOURCES["study_rooms"]
    assert fill(rooms, "hayden study rooms", TODAY)["date"] == "2026-11-05"
    assert fill(rooms, "hayden study rooms 2026-11-09", TODAY)["date"] == "2026-11-09"
    assert dated("on 2026-02-30 or 2026-03-01") == "2026-03-01"


def test_a_longer_choice_wins_the_words_it_covers():
    assert named("upper division classes", ("upper division", "division")) == ["upper division"]
    assert named("divisional", ("division",)) == []


def test_a_stored_page_answers_before_any_live_source(client, writer, live):
    word = _word()
    put = client.put(
        f"/api/knowledge/sources/pages/{word}",
        json={"category": "test", "chunks": [{"content": f"Advising is in the MU. {word}"}], "url": "https://x.edu"},
        headers=writer,
    )
    assert put.status_code == 201, put.get_json()
    result = _search(client, writer, query=word)
    assert result["from"] == "stored" and word in result["results"][0]["content"]
    assert live == []


def test_nothing_stored_goes_to_the_web(client, writer, live):
    result = _search(client, writer, query=_word())
    assert result == {"from": "live", "source": "web", "url": "https://example.edu/web", "text": "live web"}
    assert live[0][0] == "web"


def test_a_live_only_source_skips_the_stored_pages(client, writer, live):
    result = _search(client, writer, query="tempe to poly shuttle", source="shuttles")
    assert result["from"] == "live" and result["source"] == "shuttles"


def test_a_stored_source_with_nothing_stored_is_asked_live(client, writer, live):
    result = _search(client, writer, query=f"CSE 310 open seats {_word()}", source="courses")
    assert result["from"] == "live"
    key, params = live[0]
    assert key == "courses" and params["keywords"] == "CSE 310" and params["open_only"] == "true"


def test_a_failed_web_search_answers_with_what_to_do_next(client, writer, monkeypatch):
    from modules.knowledge.service import KnowledgeError

    def down(*args):
        raise KnowledgeError("Web search needs a SearXNG server", 503)

    monkeypatch.setattr(service, "query", down)
    result = _search(client, writer, query=_word())
    assert result["from"] == "none" and "SearXNG" in result["note"]


def test_a_bad_source_or_query_is_refused(client, writer, live):
    bad = client.post("/api/tools/search", json={"query": "x", "source": "nope"}, headers=writer)
    assert bad.status_code == 400
    refused = client.post("/api/tools/search", json={"query": "dining hours", "source": "dining"}, headers=writer)
    assert refused.status_code == 422 and "campus" in refused.get_json()["error"]


def test_old_pages_carry_a_note():
    now = datetime.datetime(2026, 11, 5)
    assert find._old("2026-10-01T00:00:00", now) and not find._old("2026-11-01T00:00:00", now)
    assert not find._old(None, now)
