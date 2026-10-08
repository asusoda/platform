"""Knowledge sources and hybrid search, scoped by token org plus public sources."""

import uuid

import pytest

from modules.knowledge import embedder as embedder_module
from modules.knowledge import service
from modules.knowledge.models import DIMENSIONS


def _issue(prefix, *scopes):
    from core.db import db_connect
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(db, organization_id=org_id, name="scraper", kind="app", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


@pytest.fixture
def writer(app):
    return _issue("soda", "knowledge:read", "knowledge:write")


def _vec(axis, other=None):
    """A unit vector along `axis`, tilted toward `other` when given."""
    v = [0.0] * DIMENSIONS
    v[axis] = 1.0
    if other is not None:
        v[other] = 0.3
    return v


def _word():
    return "w" + uuid.uuid4().hex[:10]


def _put(client, headers, key, chunks, **extra):
    body = {"category": "test", "chunks": chunks, **extra}
    return client.put(f"/api/knowledge/sources/{key}", json=body, headers=headers)


def _search(client, headers, query, **extra):
    response = client.post("/api/knowledge/search", json={"query": query, **extra}, headers=headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["results"]


def test_put_and_search(client, writer):
    word = _word()
    key = f"pages/{word}"
    chunks = [
        {"content": f"The library opens at 7am. {word}", "embedding": _vec(1)},
        {"content": "Parking permits are sold online.", "embedding": _vec(2)},
    ]
    created = _put(client, writer, key, chunks, embedding_model="m1", title="Hours", url="https://example.edu")
    assert created.status_code == 201, created.get_json()
    assert created.get_json()["source"]["chunk_count"] == 2

    lexical = _search(client, writer, word)
    assert lexical[0]["source_key"] == key and lexical[0]["title"] == "Hours"

    dense = _search(client, writer, "anything", embedding=_vec(2, 1), embedding_model="m1", category="test")
    assert dense and dense[0]["content"] == "Parking permits are sold online."
    other_model = _search(client, writer, "anything", embedding=_vec(2), embedding_model="m2")
    assert "Parking permits are sold online." not in [r["content"] for r in other_model]

    listed = client.get("/api/knowledge/sources?category=test", headers=writer).get_json()["sources"]
    assert key in [s["key"] for s in listed]
    assert client.get(f"/api/knowledge/sources/{key}", headers=writer).get_json()["embedding_model"] == "m1"


def test_unchanged_content_keeps_version_and_new_content_replaces(client, writer):
    old, new = _word(), _word()
    key = f"replace-{old}"
    first = _put(client, writer, key, [{"content": f"text {old}"}]).get_json()["source"]
    again = _put(client, writer, key, [{"content": f"text {old}"}], title="Renamed")
    assert again.status_code == 200
    assert again.get_json()["changed"] is False
    assert again.get_json()["source"]["version_id"] == first["version_id"]

    replaced = _put(client, writer, key, [{"content": f"text {new}"}]).get_json()
    assert replaced["changed"] is True and replaced["source"]["version_id"] != first["version_id"]
    assert _search(client, writer, old) == []
    assert _search(client, writer, new)

    assert client.delete(f"/api/knowledge/sources/{key}", headers=writer).status_code == 200
    assert _search(client, writer, new) == []
    assert client.get(f"/api/knowledge/sources/{key}", headers=writer).status_code == 404


def test_public_sources(client, writer, monkeypatch):
    ais = _issue("ais", "knowledge:read", "knowledge:write")
    public_word, private_word = _word(), _word()
    assert _put(client, ais, f"p-{public_word}", [{"content": public_word}], public=True).status_code == 403

    monkeypatch.setenv("KNOWLEDGE_PUBLISHERS", "ais")
    assert _put(client, ais, f"p-{public_word}", [{"content": public_word}], public=True).status_code == 201
    assert _put(client, ais, f"q-{private_word}", [{"content": private_word}]).status_code == 201

    seen = _search(client, writer, public_word)
    assert seen and seen[0]["public"] is True
    assert _search(client, writer, private_word) == []
    assert _search(client, ais, private_word)
    assert client.get(f"/api/knowledge/sources/q-{private_word}", headers=writer).status_code == 404


def test_tokens_are_scoped(client, officer_headers):
    reader = _issue("soda", "knowledge:read")
    body = {"category": "c", "chunks": [{"content": "x"}]}
    assert client.put("/api/knowledge/sources/k", json=body).status_code == 401
    assert client.put("/api/knowledge/sources/k", json=body, headers=officer_headers).status_code == 401
    assert client.put("/api/knowledge/sources/k", json=body, headers=reader).status_code == 403
    assert client.post("/api/knowledge/search", json={"query": "x"}, headers=reader).status_code == 200


@pytest.mark.parametrize(
    "chunks,extra",
    [
        ([{"content": "a", "embedding": [0.1, 0.2]}], {"embedding_model": "m"}),
        ([{"content": "a", "embedding": _vec(0)}, {"content": "b"}], {"embedding_model": "m"}),
        ([{"content": "a", "embedding": _vec(0)}], {}),
        ([{"content": "a", "parent_ordinal": 9}], {}),
        ([{"content": "a", "ordinal": 0}, {"content": "b", "ordinal": 0}], {}),
        ([{"content": ""}], {}),
        ([], {}),
    ],
)
def test_rejects_bad_sources(client, writer, chunks, extra):
    assert _put(client, writer, f"bad-{_word()}", chunks, **extra).status_code == 400


def test_rejects_bad_keys_and_queries(client, writer):
    assert _put(client, writer, "-starts-with-dash", [{"content": "a"}]).status_code == 400
    assert client.post("/api/knowledge/search", json={"query": ""}, headers=writer).status_code == 400
    assert client.post("/api/knowledge/search", json={"query": "x", "top_k": 0}, headers=writer).status_code == 400


def test_summary_hides_its_rows_and_window_widens(client, writer):
    word = _word()
    chunks = [
        {"ordinal": 0, "content": f"intro {word}"},
        {"ordinal": 1, "content": f"middle {word} {word}"},
        {"ordinal": 2, "content": "end"},
        {"ordinal": 3, "level": 1, "content": f"summary {word} intro middle"},
    ]
    chunks[0]["parent_ordinal"] = 3
    chunks[1]["parent_ordinal"] = 3
    _put(client, writer, f"tree-{word}", chunks)

    results = _search(client, writer, f"{word} summary intro middle")
    assert [r["content"] for r in results] == [f"summary {word} intro middle"]

    flat = f"flat-{word}"
    _put(client, writer, flat, [{"content": "before"}, {"content": f"hit {word}x"}, {"content": "after"}])
    widened = _search(client, writer, f"{word}x", window=1)
    assert widened[0]["content"] == f"before\nhit {word}x\nafter"


class FakeEmbedder:
    model = "fake"

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return [_vec(5) if "cat" in t else _vec(6) for t in texts]

    def embed_query(self, text):
        return self.embed([text])[0]


def test_platform_embeds_when_configured(client, writer, monkeypatch):
    fake = FakeEmbedder()
    monkeypatch.setattr(embedder_module, "configured", lambda: fake)
    key = f"emb-{_word()}"
    created = _put(client, writer, key, [{"content": "a cat sat"}, {"content": "a dog ran"}]).get_json()
    assert created["source"]["embedding_model"] == "fake"

    results = _search(client, writer, "kitten cat")
    assert results[0]["content"] == "a cat sat"
    assert client.post("/api/knowledge/search", json={"query": "q"}, headers=writer).get_json()["dense"] is True


def test_embedding_failure_falls_back_to_text(client, writer, monkeypatch):
    class Broken(FakeEmbedder):
        def embed(self, texts):
            raise embedder_module.EmbeddingError("down")

    monkeypatch.setattr(embedder_module, "configured", lambda: Broken())
    word = _word()
    assert _put(client, writer, f"b-{word}", [{"content": word}]).status_code == 502
    monkeypatch.setattr(embedder_module, "configured", lambda: None)
    _put(client, writer, f"b-{word}", [{"content": word}])
    monkeypatch.setattr(embedder_module, "configured", lambda: Broken())
    response = client.post("/api/knowledge/search", json={"query": word}, headers=writer).get_json()
    assert response["dense"] is False and response["results"]


def test_search_tool(client, writer):
    word = _word()
    _put(client, writer, f"tool-{word}", [{"content": f"tool text {word}"}])
    response = client.post("/api/tools/knowledge.search", json={"query": word}, headers=writer)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["result"]["results"][0]["content"] == f"tool text {word}"


def test_rrf_prefers_items_ranked_by_both_lists():
    fused = service.rrf([["a", "b", "c"], ["b", "d"]])
    assert [item for item, _ in fused][0] == "b"
