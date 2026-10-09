"""Reading a knowledge source in full: org scope, public sources, focus, pages and overlap."""

import uuid

from modules.knowledge import service

from .test_knowledge import _issue, _put


def _word():
    return "r" + uuid.uuid4().hex[:10]


def _read(client, headers, prefix, key, **params):
    return client.get(f"/api/dashboard/{prefix}/knowledge/sources/{key}", query_string=params, headers=headers)


def test_officer_reads_the_full_text_without_overlap(client, officer_headers):
    writer = _issue("soda", "knowledge:write")
    key = f"docs/{_word()}"
    chunks = [
        {"content": "Title\nFirst paragraph."},
        {"content": "First paragraph.\nSecond paragraph."},
        {"content": "Third paragraph."},
        {"ordinal": 3, "level": 1, "content": "A summary row"},
    ]
    assert _put(client, writer, key, chunks, title="Guide", url="https://example.edu/guide").status_code == 201

    response = _read(client, officer_headers, "soda", key)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["source"]["key"] == key and body["source"]["title"] == "Guide" and body["source"]["own"] is True
    assert body["source"]["url"] == "https://example.edu/guide" and body["source"]["chunk_count"] == 4
    assert [p["text"] for p in body["passages"]] == ["Title\nFirst paragraph.", "Second paragraph.", "Third paragraph."]
    assert [p["ordinal"] for p in body["passages"]] == [0, 1, 2]
    assert body["offset"] == 0 and body["next_offset"] is None and body["total"] == 3 and body["focus"] == []


def test_public_sources_are_readable_and_private_ones_are_not(client, officer_headers, monkeypatch):
    ais = _issue("ais", "knowledge:read", "knowledge:write")
    monkeypatch.setenv("KNOWLEDGE_PUBLISHERS", "ais")
    public, private = f"pub/{_word()}", f"priv/{_word()}"
    assert _put(client, ais, public, [{"content": "Open text"}], public=True).status_code == 201
    assert _put(client, ais, private, [{"content": "Closed text"}]).status_code == 201

    shared = _read(client, officer_headers, "soda", public).get_json()
    assert shared["source"]["own"] is False and shared["source"]["public"] is True and shared["source"]["crawl"] is None
    assert shared["passages"][0]["text"] == "Open text"
    assert _read(client, officer_headers, "soda", private).status_code == 404
    assert _read(client, officer_headers, "ais", private).get_json()["passages"][0]["text"] == "Closed text"

    chunk = _read(client, officer_headers, "ais", private).get_json()["passages"][0]["id"]
    assert _read(client, officer_headers, "soda", private, chunk=chunk).status_code == 404


def test_search_result_chunk_marks_its_rows(client, officer_headers):
    writer = _issue("soda", "knowledge:read", "knowledge:write")
    word = _word()
    chunks = [
        {"ordinal": 0, "content": "intro", "parent_ordinal": 3},
        {"ordinal": 1, "content": "middle", "parent_ordinal": 3},
        {"ordinal": 2, "content": "end"},
        {"ordinal": 3, "level": 1, "content": f"summary {word}"},
    ]
    key = f"tree/{word}"
    _put(client, writer, key, chunks)
    hit = client.post("/api/knowledge/search", json={"query": word}, headers=writer).get_json()["results"][0]

    body = _read(client, officer_headers, "soda", key, chunk=hit["chunk_id"]).get_json()
    by_id = {p["id"]: p["text"] for p in body["passages"]}
    assert sorted(by_id[i] for i in body["focus"]) == ["intro", "middle"]


def test_pages_start_at_the_focus_and_follow_next_offset(client, officer_headers, monkeypatch):
    monkeypatch.setattr(service, "PAGE_PASSAGES", 3)
    writer = _issue("soda", "knowledge:write")
    key = f"long/{_word()}"
    _put(client, writer, key, [{"content": f"row {i}"} for i in range(8)])

    first = _read(client, officer_headers, "soda", key).get_json()
    assert [p["text"] for p in first["passages"]] == ["row 0", "row 1", "row 2"] and first["next_offset"] == 3
    last = _read(client, officer_headers, "soda", key, offset=6).get_json()
    assert [p["text"] for p in last["passages"]] == ["row 6", "row 7"] and last["next_offset"] is None

    target = _read(client, officer_headers, "soda", key, offset=6).get_json()["passages"][1]["id"]
    focused = _read(client, officer_headers, "soda", key, chunk=target).get_json()
    assert focused["offset"] == 5 and focused["focus"] == [target]


def test_bad_reads(client, officer_headers):
    assert _read(client, officer_headers, "soda", f"none/{_word()}").status_code == 404
    writer = _issue("soda", "knowledge:write")
    key = f"bad/{_word()}"
    _put(client, writer, key, [{"content": "x"}])
    assert _read(client, officer_headers, "soda", key, offset="-1").status_code == 400
    assert _read(client, officer_headers, "soda", key, offset="x").status_code == 400
    assert _read(client, {}, "soda", key).status_code == 401


def test_read_source_tool(client):
    headers = _issue("soda", "knowledge:read", "knowledge:write")
    key = f"tool/{_word()}"
    _put(client, headers, key, [{"content": "alpha"}, {"content": "beta"}], title="Tool doc")
    response = client.post("/api/tools/knowledge.read_source", json={"key": key}, headers=headers)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["result"]
    assert result["text"] == "alpha\nbeta" and result["source"]["title"] == "Tool doc" and result["next_offset"] is None


def test_strip_overlap():
    long_tail = "x" * 50
    assert service.strip_overlap("a\nb\nc", "b\nc\nd") == "d"
    assert service.strip_overlap(f"head {long_tail}", f"{long_tail} rest") == " rest"
    assert service.strip_overlap("one", "two") == "two"
    assert service.strip_overlap("ends with a", "a b") == "a b"
