"""Packs: sync the ASU pack into knowledge, crawl with its extractors, live queries and their indexing."""

from pathlib import Path

import pytest

from core.db import db_connect
from modules.knowledge import crawl, fetch
from modules.knowledge.models import KnowledgeSource
from modules.packs import queries, service
from packs.asu import PACK
from packs.asu.sources import SOURCES

QUERIES = {q.key: q for q in PACK.queries}


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
    url = queries.url_for(QUERIES["news"], {"keywords": "robotics"})
    pages[url] = fetch.Fetched(url=url, body=b"", content_type="text/markdown", text="Robotics team wins title.")
    response = client.post(
        "/api/packs/asu/query", json={"source": "news", "params": {"keywords": "robotics"}}, headers=headers
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["url"] == url and "Robotics team wins title." in body["text"]
    assert queued[0][0] == "packs.index_result" and queued[0][1]["org_id"] == org_id

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
        result = service.index_result(db, org_id, "ais", "asu", "library_hours", url, "Hayden opens at 7am.", None)
    finally:
        db.close()
    assert result["key"] == "asu/library_hours"


def test_query_errors(client, writer, pages, queued, monkeypatch):
    headers, _ = writer
    post = lambda body: client.post("/api/packs/asu/query", json=body, headers=headers)  # noqa: E731
    assert post({"source": "nope"}).status_code == 404
    assert post({"source": "courses", "params": {"keywords": "CSE 310"}}).status_code == 422
    assert post({"source": "courses", "params": ["x"]}).status_code == 400
    assert post({"source": "library_hours"}).status_code == 502
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    assert post({"source": "web", "params": {"query": "asu"}}).status_code == 503
    assert queued == []


def test_query_list_and_tool(client, writer, pages, queued):
    headers, _ = writer
    listed = client.get("/api/packs/asu/queries", headers=headers).get_json()["queries"]
    courses = next(q for q in listed if q["key"] == "courses")
    assert any(p["name"] == "term" and p["required"] for p in courses["params"])

    url = queries.url_for(QUERIES["library_hours"], {})
    pages[url] = fetch.Fetched(url=url, body=b"", content_type="text/markdown", text="Hayden Library\nOpen 24 hours")
    result = client.post(
        "/api/tools/packs.query", json={"pack": "asu", "source": "library_hours"}, headers=headers
    ).get_json()
    assert result["result"]["url"] == url
    bad = client.post("/api/tools/packs.query", json={"pack": "nope", "source": "x"}, headers=headers)
    assert bad.status_code == 400


def test_pack_list_and_unknown_pack(client, writer):
    headers, _ = writer
    listed = client.get("/api/packs", headers=headers).get_json()["packs"]
    asu = next(p for p in listed if p["name"] == "asu")
    assert asu["key_prefix"] == "asu/" and asu["pages"] == len(SOURCES) and "courses" in asu["queries"]
    assert client.get("/api/packs/nope/queries", headers=headers).status_code == 404
    assert client.post("/api/packs/nope/sync", headers=headers).status_code == 404


def test_old_asu_routes_still_answer(client, writer, pages, queued):
    headers, _ = writer
    listed = client.get("/api/asu/queries", headers=headers).get_json()["queries"]
    assert any(q["key"] == "courses" for q in listed)
    url = queries.url_for(QUERIES["library_hours"], {})
    pages[url] = fetch.Fetched(url=url, body=b"", content_type="text/markdown", text="Hayden Library\nOpen 24 hours")
    body = client.post("/api/asu/query", json={"source": "library_hours"}, headers=headers).get_json()
    assert body["url"] == url and body["source"] == "library_hours"
    assert client.post("/api/asu/sync", headers=headers).get_json()["added"] == len(SOURCES)


def test_every_pack_feed_is_a_valid_alert_feed():
    from modules.alerts import service as alerts
    from modules.packs import catalog

    for pack in catalog.PACKS.values():
        for feed in pack.feeds:
            assert alerts.KEY_PATTERN.match(feed.key), f"{pack.name}/{feed.key}"
            assert feed.kind in alerts.KINDS, f"{pack.name}/{feed.key}"
            alerts.KINDS[feed.kind].validate(dict(feed.config))


def test_alert_presets_come_from_packs(client, officer_headers):
    presets = client.get("/api/alerts/ais/presets", headers=officer_headers).get_json()["presets"]
    internships = next(p for p in presets if p["key"] == "internships")
    assert internships["pack"] == "careers" and internships["kind"] == "github_jobs"
    assert internships["config"]["repo"] == "vanshb03/Summer2026-Internships" and internships["added"] is False
    assert client.get("/api/alerts/ais/presets").status_code == 401


def test_canvas_url_comes_from_the_pack(monkeypatch):
    from modules.accounts import providers

    monkeypatch.setenv("ACCOUNTS_BASE_URL", "https://api.test")
    monkeypatch.setenv("ACCOUNTS_CANVAS_CLIENT_ID", "id")
    monkeypatch.setenv("ACCOUNTS_CANVAS_CLIENT_SECRET", "secret")
    monkeypatch.delenv("ACCOUNTS_CANVAS_URL", raising=False)
    canvas = providers.get("canvas")
    assert canvas is not None and canvas.token_url == "https://canvas.asu.edu/login/oauth2/token"
    monkeypatch.setenv("ACCOUNTS_CANVAS_URL", "https://canvas.example.edu/")
    canvas = providers.get("canvas")
    assert canvas is not None and canvas.authorize_url == "https://canvas.example.edu/login/oauth2/auth"
