"""ASU sources in the platform: sync into knowledge, crawl with ASU extractors, live queries and their indexing."""

from pathlib import Path

import pytest

from core.db import db_connect
from modules.asu import registry, service
from modules.asu.sources import SOURCES
from modules.knowledge import crawl, fetch
from modules.knowledge.models import KnowledgeSource


def _issue(prefix, *scopes):
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(db, organization_id=org_id, name="asu", kind="app", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}, org_id
    finally:
        db.close()


@pytest.fixture
def writer(app):
    headers, org_id = _issue("ais", "knowledge:read", "knowledge:write")
    yield headers, org_id
    # Synced sources are due at once and would crowd other tests' crawl batches
    from modules.knowledge.service import delete_source

    db = db_connect.SessionLocal()
    try:
        keys = [
            s.key
            for s in db.query(KnowledgeSource).filter(
                KnowledgeSource.organization_id == org_id,
                KnowledgeSource.key.like("asu/%") | KnowledgeSource.key.like("asu-live/%"),
            )
        ]
        for key in keys:
            delete_source(db, org_id, key)
    finally:
        db.close()


@pytest.fixture
def queued(monkeypatch):
    calls: list = []
    monkeypatch.setattr(service, "defer", lambda name, **kwargs: calls.append((name, kwargs)))
    return calls


@pytest.fixture
def pages(monkeypatch):
    served: dict = {}

    def fake_fetch(url):
        page = served.get(url, fetch.FetchError(f"{url} is not served in this test"))
        if isinstance(page, Exception):
            raise page
        return page

    monkeypatch.setattr(fetch, "fetch", fake_fetch)
    return served


def _sources(org_id):
    db = db_connect.SessionLocal()
    try:
        rows = db.query(KnowledgeSource).filter(
            KnowledgeSource.organization_id == org_id, KnowledgeSource.key.like("asu/%")
        )
        return {s.key: (s.url, s.enabled, s.extractor, s.fetch_every_hours) for s in rows}
    finally:
        db.close()


def test_sync_registers_every_page_and_retires_removed_ones(client, writer):
    headers, org_id = writer
    first = client.post("/api/asu/sync", headers=headers).get_json()
    assert first["added"] + first["updated"] == len(SOURCES)
    rows = _sources(org_id)
    assert len(rows) == len(SOURCES)
    url, enabled, extractor, every = rows["asu/library_hours"]
    assert url == SOURCES["library_hours"].url and enabled and extractor == "asu.library_hours"
    assert every == SOURCES["library_hours"].fetch_every_hours

    db = db_connect.SessionLocal()
    try:
        db.add(KnowledgeSource(organization_id=org_id, key="asu/removed", url="https://asu.edu/x", category="c"))
        db.commit()
    finally:
        db.close()
    again = client.post("/api/asu/sync", headers=headers).get_json()
    assert again["added"] == 0 and again["retired"] == 1
    assert _sources(org_id)["asu/removed"][1] is False


def test_sync_needs_write_scope(client, app):
    reader, _ = _issue("ais", "knowledge:read")
    assert client.post("/api/asu/sync", headers=reader).status_code == 403


def test_crawl_uses_the_asu_extractor(client, writer, pages):
    headers, org_id = writer
    client.post("/api/asu/sync", headers=headers)
    url = SOURCES["library_hours"].url
    markdown = (Path(__file__).parent / "asu_fixtures" / "library_hours.md").read_text()
    pages[url] = fetch.Fetched(url=url, body=markdown.encode(), content_type="text/markdown", text=markdown)
    db = db_connect.SessionLocal()
    try:
        result = crawl.run(db, org_id, "asu/library_hours", None)
    finally:
        db.close()
    assert result["changed"] is True
    found = client.post("/api/knowledge/search", json={"query": "Hayden Library"}, headers=headers).get_json()
    hayden = [r for r in found["results"] if "Hayden Library" in r["content"]]
    assert hayden and "|" not in hayden[0]["content"].split("\n", 1)[1]


def test_live_query_answers_then_queues_indexing(client, writer, pages, queued):
    headers, org_id = writer
    url = registry.url_for(registry.QUERY_SOURCES["news"], {"keywords": "robotics"})
    pages[url] = fetch.Fetched(url=url, body=b"", content_type="text/markdown", text="Robotics team wins title.")
    response = client.post(
        "/api/asu/query", json={"source": "news", "params": {"keywords": "robotics"}}, headers=headers
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["url"] == url and "Robotics team wins title." in body["text"]
    assert queued[0][0] == "asu.index_result" and queued[0][1]["org_id"] == org_id

    db = db_connect.SessionLocal()
    try:
        first = service.index_result(db, **queued[0][1], embedder=None)
        again = service.index_result(db, **queued[0][1], embedder=None)
    finally:
        db.close()
    assert first["changed"] is True and first["key"].startswith("asu-live/news-")
    assert again == {"key": first["key"], "changed": False}
    found = client.post("/api/knowledge/search", json={"query": "Robotics"}, headers=headers).get_json()
    assert any("Robotics team wins title." in r["content"] for r in found["results"])


def test_live_result_for_a_scheduled_page_updates_that_source(client, writer):
    headers, org_id = writer
    client.post("/api/asu/sync", headers=headers)
    db = db_connect.SessionLocal()
    try:
        url = SOURCES["library_hours"].url
        result = service.index_result(db, org_id, "ais", "library_hours", url, "Hayden opens at 7am.", None)
    finally:
        db.close()
    assert result["key"] == "asu/library_hours"


def test_query_errors(client, writer, pages, queued, monkeypatch):
    headers, _ = writer
    post = lambda body: client.post("/api/asu/query", json=body, headers=headers)  # noqa: E731
    assert post({"source": "nope"}).status_code == 404
    assert post({"source": "courses", "params": {"keywords": "CSE 310"}}).status_code == 422
    assert post({"source": "courses", "params": ["x"]}).status_code == 400
    assert post({"source": "library_hours"}).status_code == 502
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    assert post({"source": "web", "params": {"query": "asu"}}).status_code == 503
    assert queued == []


def test_query_list_and_tool(client, writer, pages, queued):
    headers, _ = writer
    listed = client.get("/api/asu/queries", headers=headers).get_json()["queries"]
    courses = next(q for q in listed if q["key"] == "courses")
    assert any(p["name"] == "term" and p["required"] for p in courses["params"])

    url = registry.url_for(registry.QUERY_SOURCES["library_hours"], {})
    pages[url] = fetch.Fetched(url=url, body=b"", content_type="text/markdown", text="Hayden Library\nOpen 24 hours")
    result = client.post("/api/tools/asu.query", json={"source": "library_hours"}, headers=headers).get_json()
    assert result["result"]["url"] == url
    bad = client.post("/api/tools/asu.query", json={"source": "nope"}, headers=headers)
    assert bad.status_code == 400
