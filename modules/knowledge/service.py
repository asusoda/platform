"""Knowledge sources, their versions and chunks. No Flask here.

Writers (a scraper, an import script) send a source as chunks, or crawl.py fetches a crawled source.
A source is replaced whole: when its content hash changes, a new version and its chunks replace the
old ones. Only organizations listed in KNOWLEDGE_PUBLISHERS may write public sources. search.py
searches the chunks.
"""

import hashlib
import math
import os
import re
from typing import Any

from core.errors import ServiceError
from core.time import iso, utcnow
from modules.auth import scopes
from modules.knowledge.embedder import Embedder, EmbeddingError
from modules.knowledge.models import DIMENSIONS, KnowledgeChunk, KnowledgeSource, KnowledgeVersion

scopes.declare("knowledge:read", "Search the organization's knowledge and public sources")
scopes.declare("knowledge:write", "Write and delete the organization's knowledge sources")

MAX_CHUNKS = 5000
MAX_CHUNK_CHARS = 20000
MAX_LEVEL = 10
KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")


class KnowledgeError(ServiceError, ValueError):
    pass


def can_publish(org_prefix: str) -> bool:
    publishers = {p.strip() for p in os.environ.get("KNOWLEDGE_PUBLISHERS", "").split(",") if p.strip()}
    return org_prefix in publishers


def _vector(value: Any, field: str) -> list[float]:
    if not isinstance(value, list) or len(value) != DIMENSIONS:
        raise KnowledgeError(f"{field} must be a list of {DIMENSIONS} numbers")
    try:
        vector = [float(x) for x in value]
    except (TypeError, ValueError):
        raise KnowledgeError(f"{field} must be a list of {DIMENSIONS} numbers") from None
    if not all(math.isfinite(x) for x in vector):
        raise KnowledgeError(f"{field} must hold finite numbers")
    return vector


def _text(value: Any, field: str, limit: int, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise KnowledgeError(f"{field} must be a non-empty string of at most {limit} characters")
    return value.strip()


def _source_dict(source: KnowledgeSource, version: KnowledgeVersion | None = None) -> dict:
    return {
        "id": source.id,
        "key": source.key,
        "url": source.url,
        "title": source.title,
        "category": source.category,
        "public": bool(source.public),
        "version_id": source.current_version_id,
        "content_hash": version.content_hash if version else None,
        "embedding_model": version.embedding_model if version else None,
        "chunk_count": version.chunk_count if version else 0,
        "fetched_at": iso(version.fetched_at) if version else None,
        "updated_at": iso(source.updated_at),
        "crawl": None
        if source.fetch_every_hours is None
        else {
            "fetch_every_hours": source.fetch_every_hours,
            "extractor": source.extractor,
            "enabled": bool(source.enabled),
            "last_attempt_at": iso(source.last_attempt_at),
            "last_error": source.last_error,
        },
    }


def _validate_chunks(chunks: Any) -> list[dict]:
    if not isinstance(chunks, list) or not chunks or len(chunks) > MAX_CHUNKS:
        raise KnowledgeError(f"chunks must be a list of 1 to {MAX_CHUNKS} items")
    rows: list[dict] = []
    ordinals: set[int] = set()
    for i, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise KnowledgeError(f"chunks[{i}] must be an object")
        ordinal = chunk.get("ordinal", i)
        level = chunk.get("level", 0)
        parent = chunk.get("parent_ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0 or ordinal in ordinals:
            raise KnowledgeError(f"chunks[{i}].ordinal must be a unique non-negative integer")
        if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= MAX_LEVEL:
            raise KnowledgeError(f"chunks[{i}].level must be an integer from 0 to {MAX_LEVEL}")
        if parent is not None and (not isinstance(parent, int) or isinstance(parent, bool)):
            raise KnowledgeError(f"chunks[{i}].parent_ordinal must be an integer")
        ordinals.add(ordinal)
        embedding = chunk.get("embedding")
        rows.append(
            {
                "ordinal": ordinal,
                "level": level,
                "parent_ordinal": parent,
                "content": _text(chunk.get("content"), f"chunks[{i}].content", MAX_CHUNK_CHARS),
                "embedding": None if embedding is None else _vector(embedding, f"chunks[{i}].embedding"),
            }
        )
    for i, row in enumerate(rows):
        if row["parent_ordinal"] is not None and row["parent_ordinal"] not in ordinals:
            raise KnowledgeError(f"chunks[{i}].parent_ordinal names no chunk")
    with_vectors = sum(row["embedding"] is not None for row in rows)
    if with_vectors not in (0, len(rows)):
        raise KnowledgeError("Either every chunk has an embedding or none does")
    return rows


def _content_hash(rows: list[dict]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda r: r["ordinal"]):
        digest.update(f"{row['ordinal']}:{row['level']}:{row['parent_ordinal']}:".encode())
        digest.update(row["content"].encode())
        digest.update(b"\0")
    return digest.hexdigest()


def _drop_versions(db, source_id: Any, keep: Any = None) -> None:
    """Delete a source's versions and their chunks, except `keep`. Explicit, since SQLite may not cascade."""
    versions = db.query(KnowledgeVersion.id).filter(KnowledgeVersion.source_id == source_id)
    if keep is not None:
        versions = versions.filter(KnowledgeVersion.id != keep)
    ids = [row[0] for row in versions.all()]
    if ids:
        db.query(KnowledgeChunk).filter(KnowledgeChunk.version_id.in_(ids)).delete(synchronize_session=False)
        db.query(KnowledgeVersion).filter(KnowledgeVersion.id.in_(ids)).delete(synchronize_session=False)


def put_source(db, org_id: int, org_prefix: str, key: str, data: dict, embedder: Embedder | None) -> dict:
    """Create or replace a source from untrusted input. Commits. Returns the source and whether it changed."""
    if not isinstance(key, str) or not KEY_PATTERN.match(key):
        raise KnowledgeError("key must be 1 to 255 letters, digits or ._:/- and start with a letter or digit")
    category = _text(data.get("category"), "category", 100)
    title = _text(data.get("title"), "title", 500, required=False)
    url = _text(data.get("url"), "url", 2000, required=False)
    public = data.get("public", False)
    if not isinstance(public, bool):
        raise KnowledgeError("public must be true or false")
    if public and not can_publish(org_prefix):
        raise KnowledgeError("This organization may not write public sources", 403)
    rows = _validate_chunks(data.get("chunks"))
    content_hash = data.get("content_hash")
    if content_hash is None:
        content_hash = _content_hash(rows)
    elif not isinstance(content_hash, str) or not 0 < len(content_hash) <= 64:
        raise KnowledgeError("content_hash must be a string of at most 64 characters")

    source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if source is None:
        source = KnowledgeSource(organization_id=org_id, key=key, category=category)
        db.add(source)
        db.flush()
    current = db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first()
    source.title, source.url, source.category, source.public = title, url, category, public
    source.updated_at = utcnow()

    if current is not None and current.content_hash == content_hash:
        db.query(KnowledgeChunk).filter_by(version_id=current.id).update(
            {"category": category, "public": public}, synchronize_session=False
        )
        db.commit()
        return {"source": _source_dict(source, current), "changed": False}

    model = None
    if rows[0]["embedding"] is not None:
        model = _text(data.get("embedding_model"), "embedding_model", 200)
    else:
        model = _embed(rows, embedder)
    version = _write_version(db, source, rows, content_hash, model)
    db.commit()
    return {"source": _source_dict(source, version), "changed": True}


def _embed(rows: list[dict], embedder: Embedder | None) -> str | None:
    """Fill each row's embedding from the embedder. Returns the model name, or None without one."""
    if embedder is None:
        return None
    try:
        vectors = embedder.embed([row["content"] for row in rows])
    except EmbeddingError as e:
        raise KnowledgeError(str(e), 502) from e
    for row, vector in zip(rows, vectors, strict=True):
        row["embedding"] = _vector(vector, "embedding from the embedding service")
    return embedder.model


def _write_version(
    db, source: KnowledgeSource, rows: list[dict], content_hash: str, model: str | None, text_chars: int | None = None
) -> KnowledgeVersion:
    """Store rows as the source's new current version and drop the old ones. Flushes, does not commit."""
    version = KnowledgeVersion(
        source_id=source.id,
        content_hash=content_hash,
        embedding_model=model,
        chunk_count=len(rows),
        text_chars=text_chars,
    )
    db.add(version)
    db.flush()
    db.add_all(
        KnowledgeChunk(
            organization_id=source.organization_id,
            source_id=source.id,
            version_id=version.id,
            category=source.category,
            public=source.public,
            fetched_at=version.fetched_at,
            **row,
        )
        for row in rows
    )
    source.current_version_id = version.id
    db.flush()
    _drop_versions(db, source.id, keep=version.id)
    return version


def _find(db, org_id: int, key: str) -> KnowledgeSource:
    source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if source is None:
        raise KnowledgeError("No source with this key", 404)
    return source


def get_source(db, org_id: int, key: str) -> dict:
    source = _find(db, org_id, key)
    return _source_dict(source, db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first())


def list_sources(db, org_id: int, category: str | None = None) -> list[dict]:
    query = db.query(KnowledgeSource, KnowledgeVersion).outerjoin(
        KnowledgeVersion, KnowledgeVersion.id == KnowledgeSource.current_version_id
    )
    query = query.filter(KnowledgeSource.organization_id == org_id)
    if category:
        query = query.filter(KnowledgeSource.category == category)
    return [_source_dict(s, v) for s, v in query.order_by(KnowledgeSource.key).all()]


def delete_source(db, org_id: int, key: str) -> None:
    source = _find(db, org_id, key)
    _drop_versions(db, source.id)
    db.delete(source)
    db.commit()
