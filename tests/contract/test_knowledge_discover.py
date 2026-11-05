"""Pages an agent read: saved at once on an ASU host, held for an officer elsewhere."""

import pytest

from core.db import db_connect
from modules.knowledge import crawl
from modules.knowledge.models import KnowledgeSource
from tests.contract.test_knowledge_crawl import _issue


@pytest.fixture
def agent(app):
    return _issue("ais", "knowledge:discover")


@pytest.fixture(autouse=True)
def _cleanup(app):
    yield
    db = db_connect.SessionLocal()
    try:
        db.query(KnowledgeSource).filter(KnowledgeSource.key.like("read/%") | (KnowledgeSource.key == "news-a")).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def _source(key):
    db = db_connect.SessionLocal()
    try:
        return db.query(KnowledgeSource).filter_by(key=key).one()
    finally:
        db.close()


def _due_keys():
    db = db_connect.SessionLocal()
    try:
        return {s.key for s in crawl.due(db, limit=1000)}
    finally:
        db.close()


def test_asu_page_is_saved_and_crawled(client, agent):
    url = "https://Catalog.Apps.ASU.edu/catalog/classes?term=2261#top"
    response = client.post("/api/knowledge/discovered", json={"url": url}, headers=agent)
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "added" and body["key"].startswith("read/catalog.apps.asu.edu/")
    source = _source(body["key"])
    assert source.url == "https://catalog.apps.asu.edu/catalog/classes?term=2261"
    assert source.enabled and source.review is None and source.fetch_every_hours == 168
    assert source.category == "asu"
    assert body["key"] in _due_keys()

    again = client.post("/api/knowledge/discovered", json={"url": url}, headers=agent)
    assert again.status_code == 200 and again.get_json() == {"key": body["key"], "status": "known"}


def test_other_page_waits_on_an_officer(client, agent, officer_headers):
    url = "https://example.org/guide"
    body = client.post("/api/knowledge/discovered", json={"url": url}, headers=agent).get_json()
    assert body["status"] == "review"
    key = body["key"]
    assert _source(key).review == "pending" and key not in _due_keys()

    listed = client.get("/api/dashboard/ais/knowledge/sources", headers=officer_headers).get_json()["sources"]
    assert next(s for s in listed if s["key"] == key)["crawl"]["review"] == "pending"

    base = f"/api/dashboard/ais/knowledge/sources/{key}/review"
    rejected = client.post(base, json={"approve": False}, headers=officer_headers)
    assert rejected.status_code == 200 and rejected.get_json()["review"] == "rejected"
    known = client.post("/api/knowledge/discovered", json={"url": url}, headers=agent).get_json()
    assert known["status"] == "known" and _source(key).review == "rejected"

    approved = client.post(base, json={"approve": True}, headers=officer_headers).get_json()
    assert approved == {"key": key, "review": None, "enabled": True}
    assert key in _due_keys()
    assert client.post(base, json={"approve": True}, headers=officer_headers).status_code == 409


def test_category_follows_the_host(client, agent, officer_headers):
    body = {"url": "https://news.example.edu/a", "category": "news", "fetch_every_hours": 24}
    assert (
        client.put("/api/dashboard/ais/knowledge/crawls/news-a", json=body, headers=officer_headers).status_code == 200
    )
    key = client.post(
        "/api/knowledge/discovered", json={"url": "https://news.example.edu/b"}, headers=agent
    ).get_json()["key"]
    assert _source(key).category == "news"


@pytest.mark.parametrize(
    "url", ["ftp://asu.edu/x", "https://user:pw@asu.edu/x", "https://localhost/x", "", 5, "https://" + "a" * 2000]
)
def test_bad_urls_are_refused(client, agent, url):
    assert client.post("/api/knowledge/discovered", json={"url": url}, headers=agent).status_code == 400


def test_scope_is_needed(client, app):
    reader = _issue("ais", "knowledge:read")
    assert (
        client.post("/api/knowledge/discovered", json={"url": "https://asu.edu/x"}, headers=reader).status_code == 403
    )
