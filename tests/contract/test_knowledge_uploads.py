"""Uploaded documents, per-org knowledge settings and the run log, through the dashboard routes. No network."""

import io
import uuid
import zipfile

import pytest

BASE = "/api/dashboard/ais/knowledge"


@pytest.fixture
def queued(monkeypatch):
    import core.jobs

    calls = []
    monkeypatch.setattr(core.jobs, "defer", lambda name, **kwargs: calls.append((name, kwargs)))
    return calls


@pytest.fixture
def folder(client, officer_headers):
    """A fresh folder; its sources are deleted after the test."""
    name = "t" + uuid.uuid4().hex[:8]
    yield name
    for source in client.get(f"{BASE}/sources", headers=officer_headers).get_json()["sources"]:
        if source["key"].startswith(f"{name}/"):
            client.delete(f"{BASE}/sources/{source['key']}", headers=officer_headers)


@pytest.fixture
def reset_settings(client, officer_headers):
    yield
    nulls = dict.fromkeys(("chunk_chars", "chunk_overlap", "mode", "top_k", "window", "max_distance", "rrf_k"))
    client.put(f"{BASE}/settings", json=nulls, headers=officer_headers)


def _docx(*paragraphs: str) -> bytes:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", f'<w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>')
    return buffer.getvalue()


def _pdf(line: str) -> bytes:
    """A one-page PDF with one line of text."""
    stream = f"BT /F1 18 Tf 20 100 Td ({line}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%b\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n%b\nendobj\n" % (number, body))
    xref = out.tell()
    out.write(b"xref\n0 6\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % o for o in offsets))
    out.write(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % xref)
    return out.getvalue()


def _upload(client, headers, files, **form):
    data = {**form, "files": [(io.BytesIO(body), name) for name, body in files]}
    return client.post(f"{BASE}/documents", data=data, headers=headers, content_type="multipart/form-data")


def test_batch_upload_indexes_each_file(client, officer_headers, folder):
    files = [
        ("Handbook.md", b"# Handbook\n\nMeetings are on Tuesdays in the zebra room."),
        ("faq.html", b"<html><head><title>FAQ</title></head><body><p>Dues are paid in October.</p></body></html>"),
        ("Bylaws.docx", _docx("Article one.", "Officers serve one year.")),
        ("Hours.pdf", _pdf("Office hours are Fridays")),
        ("broken.pdf", b"not a pdf"),
        ("photo.png", b"\x89PNG"),
    ]
    response = _upload(client, officer_headers, files, folder=folder, category="club")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    by_file = {f["file"]: f for f in body["files"]}
    assert (body["indexed"], body["unchanged"], body["failed"]) == (4, 0, 2)
    assert by_file["Handbook.md"]["key"] == f"{folder}/handbook.md" and by_file["Handbook.md"]["chunks"] >= 1
    assert by_file["Hours.pdf"]["chunks"] == 1
    assert by_file["broken.pdf"]["error"] == "The PDF could not be read"
    assert "file types" in by_file["photo.png"]["error"]

    sources = {s["key"]: s for s in client.get(f"{BASE}/sources", headers=officer_headers).get_json()["sources"]}
    assert sources[f"{folder}/faq.html"]["title"] == "FAQ"
    assert sources[f"{folder}/bylaws.docx"]["category"] == "club" and sources[f"{folder}/bylaws.docx"]["crawl"] is None
    assert f"{folder}/photo.png" not in sources

    found = client.post(f"{BASE}/search", json={"query": "zebra room"}, headers=officer_headers).get_json()
    assert found["results"][0]["source_key"] == f"{folder}/handbook.md"

    again = _upload(client, officer_headers, files[:1], folder=folder, category="club").get_json()
    assert (again["indexed"], again["unchanged"]) == (0, 1)

    logged = client.get(f"{BASE}/runs?limit=10", headers=officer_headers).get_json()["runs"]
    mine = [r for r in logged if r["source_key"].startswith(f"{folder}/")]
    assert mine[0]["kind"] == "upload" and mine[0]["changed"] is False
    failed = client.get(f"{BASE}/runs?failed=1", headers=officer_headers).get_json()["runs"]
    assert any(r["source_key"] == f"{folder}/broken.pdf" for r in failed)


def test_upload_refusals(client, officer_headers, folder):
    assert _upload(client, officer_headers, [], folder=folder).status_code == 400
    many = [(f"f{i}.txt", b"x") for i in range(21)]
    assert _upload(client, officer_headers, many, folder=folder).status_code == 400
    assert _upload(client, officer_headers, [("a.txt", b"x")], folder="Bad Folder").status_code == 400
    public = _upload(client, officer_headers, [("a.txt", b"text")], folder=folder, public="true")
    assert public.status_code == 403


def test_settings_change_chunking_and_search(client, officer_headers, folder, reset_settings):
    got = client.get(f"{BASE}/settings", headers=officer_headers).get_json()
    assert got["settings"] == got["defaults"] and got["settings"]["mode"] == "hybrid"
    assert got["embeddings"]["configured"] is False and got["embeddings"]["model"] is None
    assert got["embeddings"]["status"]["stale"] == 0

    for bad in ({"chunk_chars": 50}, {"mode": "magic"}, {"max_distance": 3}, {"nope": 1}, {"chunk_overlap": 900}, {}):
        assert client.put(f"{BASE}/settings", json=bad, headers=officer_headers).status_code == 400, bad

    saved = client.put(f"{BASE}/settings", json={"chunk_chars": 100, "top_k": 1}, headers=officer_headers)
    assert saved.status_code == 200 and saved.get_json()["settings"]["chunk_chars"] == 100

    text = "\n".join(f"Paragraph {i} says the walrus meets at noon on day {i}." for i in range(20)).encode()
    first = _upload(client, officer_headers, [("walrus.txt", text)], folder=folder).get_json()["files"][0]
    assert first["chunks"] > 5

    found = client.post(f"{BASE}/search", json={"query": "walrus noon"}, headers=officer_headers).get_json()
    assert len(found["results"]) == 1

    client.put(f"{BASE}/settings", json={"chunk_chars": 2000}, headers=officer_headers)
    second = _upload(client, officer_headers, [("walrus.txt", text)], folder=folder).get_json()["files"][0]
    assert second["changed"] is True and second["chunks"] < first["chunks"]

    reset = client.put(f"{BASE}/settings", json={"chunk_chars": None, "top_k": None}, headers=officer_headers)
    assert reset.get_json()["settings"] == reset.get_json()["defaults"]


def test_reindex_queues_a_job(client, officer_headers, queued):
    assert client.post(f"{BASE}/reindex", headers=officer_headers).status_code == 202
    assert queued[-1][0] == "knowledge.reindex"


def test_crawls_are_logged(app, monkeypatch):
    from core.db import db_connect
    from modules.knowledge import crawl, fetch, runs
    from modules.knowledge.models import KnowledgeSource
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix="ais").scalar()
        key = "logged-" + uuid.uuid4().hex[:8]
        source = KnowledgeSource(
            organization_id=org_id, key=key, url="https://example.invalid/", category="x", fetch_every_hours=24
        )
        db.add(source)
        db.commit()

        def refuse(url):
            raise fetch.FetchRejected("robots.txt disallows this page")

        monkeypatch.setattr(fetch, "fetch", refuse)
        crawl.crawl(db, source, None)
        logged = [r for r in runs.recent(db, org_id) if r["source_key"] == key]
        assert logged[0]["kind"] == "crawl" and logged[0]["error"] == "robots.txt disallows this page"
        db.delete(source)
        db.commit()
    finally:
        db.close()
