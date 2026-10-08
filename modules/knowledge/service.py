"""Knowledge sources and hybrid search over their chunks. No Flask here.

Writers (a scraper, an import script) send a source as chunks; the platform does not fetch pages.
A source is replaced whole: when its content hash changes, a new version and its chunks replace the
old ones. Search fuses a vector leg and a text leg with reciprocal rank fusion over the caller's organization
plus public sources. Only organizations listed in KNOWLEDGE_PUBLISHERS may write public sources.

On Postgres with pgvector, both legs run in SQL. Elsewhere, including Postgres without pgvector,
the vector leg runs in Python over the stored vectors, and on SQLite so does the text leg.
"""

import datetime
import hashlib
import math
import os
import re
from typing import Any

from sqlalchemy import or_, text

from core.errors import ServiceError
from core.logging_config import get_logger
from modules.auth import scopes
from modules.knowledge.embedder import Embedder, EmbeddingError
from modules.knowledge.models import DIMENSIONS, Embedding, KnowledgeChunk, KnowledgeSource, KnowledgeVersion

logger = get_logger("knowledge")

scopes.declare("knowledge:read", "Search the organization's knowledge and public sources")
scopes.declare("knowledge:write", "Write and delete the organization's knowledge sources")

MAX_CHUNKS = 5000
MAX_CHUNK_CHARS = 20000
MAX_LEVEL = 10
MAX_TOP_K = 50
MAX_WINDOW = 5
CANDIDATES = 50
RRF_K = 60.0
KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")
TEXT_CONFIG = "english"


class KnowledgeError(ServiceError, ValueError):
    pass


def max_distance() -> float:
    """Cosine distance above which a vector match is dropped. KNOWLEDGE_MAX_DISTANCE, default 0.6."""
    try:
        value = float(os.environ.get("KNOWLEDGE_MAX_DISTANCE", "0.6"))
    except ValueError:
        return 0.6
    return value if 0 < value <= 2 else 0.6


def can_publish(org_prefix: str) -> bool:
    publishers = {p.strip() for p in os.environ.get("KNOWLEDGE_PUBLISHERS", "").split(",") if p.strip()}
    return org_prefix in publishers


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


_PGVECTOR: dict[str, bool] = {}


def _dialect(db) -> str:
    return db.get_bind().dialect.name


def _vector_sql(db) -> bool:
    """Whether the vector leg can run in SQL: Postgres with the embedding column as pgvector."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    url = str(bind.url)
    if url not in _PGVECTOR:
        row = db.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'knowledge_chunks' AND column_name = 'embedding'"
            )
        ).first()
        _PGVECTOR[url] = row is not None and row[0] == "USER-DEFINED"
    return _PGVECTOR[url]


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
        "fetched_at": _iso(version.fetched_at) if version else None,
        "updated_at": _iso(source.updated_at),
        "crawl": None
        if source.fetch_every_hours is None
        else {
            "fetch_every_hours": source.fetch_every_hours,
            "extractor": source.extractor,
            "enabled": bool(source.enabled),
            "last_attempt_at": _iso(source.last_attempt_at),
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
    source.updated_at = _now()

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


# Search


def _scope(query, org_id: int, category: str | None):
    query = query.filter(or_(KnowledgeChunk.organization_id == org_id, KnowledgeChunk.public.is_(True)))
    return query.filter(KnowledgeChunk.category == category) if category else query


def _dense_sql(db, org_id: int, category: str | None, vector: list[float], model: str) -> list[str]:
    params: dict[str, Any] = {
        "org": org_id,
        "vec": Embedding().process_bind_param(vector, None),
        "model": model,
        "n": CANDIDATES,
        "max": max_distance(),
    }
    where = "(c.organization_id = :org OR c.public) AND c.embedding IS NOT NULL AND v.embedding_model = :model"
    if category:
        where += " AND c.category = :category"
        params["category"] = category
    sql = (
        "SELECT id FROM ("  # nosec B608 - only fixed fragments are formatted
        " SELECT c.id, c.embedding <=> CAST(:vec AS vector) AS distance"
        " FROM knowledge_chunks c JOIN knowledge_versions v ON v.id = c.version_id"
        f" WHERE {where} ORDER BY distance LIMIT :n"
        ") nearest WHERE distance <= :max"
    )
    return [row[0] for row in db.execute(text(sql), params)]


def _dense_python(db, org_id: int, category: str | None, vector: list[float], model: str) -> list[str]:
    query = db.query(KnowledgeChunk.id, KnowledgeChunk.embedding).join(
        KnowledgeVersion, KnowledgeVersion.id == KnowledgeChunk.version_id
    )
    query = _scope(query, org_id, category).filter(
        KnowledgeVersion.embedding_model == model, KnowledgeChunk.embedding.isnot(None)
    )
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    limit = max_distance()
    scored = []
    for chunk_id, embedding in query.all():
        other = math.sqrt(sum(x * x for x in embedding)) or 1.0
        distance = 1.0 - sum(a * b for a, b in zip(vector, embedding, strict=False)) / (norm * other)
        if distance <= limit:
            scored.append((distance, chunk_id))
    scored.sort()
    return [chunk_id for _, chunk_id in scored[:CANDIDATES]]


def _lexical_sql(db, org_id: int, category: str | None, query_text: str) -> list[str]:
    params: dict[str, Any] = {"org": org_id, "q": query_text, "n": CANDIDATES}
    where = "(c.organization_id = :org OR c.public)"
    if category:
        where += " AND c.category = :category"
        params["category"] = category
    tsv = f"to_tsvector('{TEXT_CONFIG}', c.content)"
    tsq = f"websearch_to_tsquery('{TEXT_CONFIG}', :q)"
    sql = (
        f"SELECT c.id FROM knowledge_chunks c WHERE {where} AND {tsv} @@ {tsq}"  # nosec B608 - fixed fragments
        f" ORDER BY ts_rank_cd({tsv}, {tsq}) DESC LIMIT :n"
    )
    return [row[0] for row in db.execute(text(sql), params)]


def _terms(value: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", value.lower()) if len(t) > 1}


def _lexical_python(db, org_id: int, category: str | None, query_text: str) -> list[str]:
    terms = _terms(query_text)
    if not terms:
        return []
    query = _scope(db.query(KnowledgeChunk.id, KnowledgeChunk.content), org_id, category)
    scored = []
    for chunk_id, content in query.all():
        score = len(terms & _terms(content))
        if score:
            scored.append((-score, chunk_id))
    scored.sort()
    return [chunk_id for _, chunk_id in scored[:CANDIDATES]]


def rrf(lists: list[list[str]], k: float = RRF_K) -> list[tuple[str, float]]:
    """Reciprocal rank fusion. Each ranked list contributes 1 / (k + rank)."""
    scores: dict[str, float] = {}
    for ranked in lists:
        for rank, item in enumerate(ranked):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


def _int(value: Any, field: str, default: int, low: int, high: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise KnowledgeError(f"{field} must be an integer from {low} to {high}")
    return value


def search(
    db,
    org_id: int,
    query: Any,
    *,
    category: Any = None,
    top_k: Any = None,
    window: Any = None,
    embedding: Any = None,
    embedding_model: Any = None,
    embedder: Embedder | None = None,
) -> dict:
    """Ranked passages for a query from the org's sources and public ones. Arguments come from callers."""
    query_text = _text(query, "query", 1000) or ""
    category = _text(category, "category", 100, required=False)
    top_k = _int(top_k, "top_k", 8, 1, MAX_TOP_K)
    window = _int(window, "window", 0, 0, MAX_WINDOW)

    vector, model = None, None
    if embedding is not None:
        vector = _vector(embedding, "embedding")
        model = _text(embedding_model, "embedding_model", 200)
    elif embedder is not None:
        try:
            vector, model = _vector(embedder.embed_query(query_text), "query embedding"), embedder.model
        except (EmbeddingError, KnowledgeError):
            logger.warning("query embedding failed, searching on text only")

    legs: list[list[str]] = []
    if vector is not None and model is not None:
        dense = _dense_sql if _vector_sql(db) else _dense_python
        legs.append(dense(db, org_id, category, vector, model))
    lexical = _lexical_sql if _dialect(db) == "postgresql" else _lexical_python
    legs.append(lexical(db, org_id, category, query_text))

    fused = rrf(legs)
    if not fused:
        return {"results": [], "dense": vector is not None}
    rows = {
        chunk.id: (chunk, source)
        for chunk, source in db.query(KnowledgeChunk, KnowledgeSource)
        .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
        .filter(KnowledgeChunk.id.in_([chunk_id for chunk_id, _ in fused]))
        .all()
    }

    # A row whose summary already ranked higher adds nothing.
    seen: set[tuple[str, int]] = set()
    ordered = []
    for chunk_id, score in fused:
        if chunk_id not in rows:
            continue
        chunk, source = rows[chunk_id]
        if chunk.parent_ordinal is not None and (chunk.version_id, chunk.parent_ordinal) in seen:
            continue
        seen.add((chunk.version_id, chunk.ordinal))
        ordered.append((chunk, source, score))
        if len(ordered) == top_k:
            break

    return {"results": _widen(db, ordered, window), "dense": vector is not None}


def _widen(db, ordered: list, window: int) -> list[dict]:
    """Each hit as evidence; page text hits carry `window` neighbors on each side, without repeats."""
    covered: dict[str, list[tuple[int, int]]] = {}
    results = []
    for chunk, source, score in ordered:
        content = chunk.content
        if window and chunk.level == 0:
            spans = covered.setdefault(chunk.version_id, [])
            if any(lo <= chunk.ordinal <= hi for lo, hi in spans):
                continue
            lo, hi = chunk.ordinal - window, chunk.ordinal + window
            spans.append((lo, hi))
            neighbors = (
                db.query(KnowledgeChunk.content)
                .filter(
                    KnowledgeChunk.version_id == chunk.version_id,
                    KnowledgeChunk.level == 0,
                    KnowledgeChunk.ordinal.between(lo, hi),
                )
                .order_by(KnowledgeChunk.ordinal)
                .all()
            )
            content = "\n".join(row[0] for row in neighbors) or content
        results.append(
            {
                "chunk_id": chunk.id,
                "source_key": source.key,
                "title": source.title,
                "url": source.url,
                "category": chunk.category,
                "public": bool(chunk.public),
                "content": content,
                "score": round(score, 6),
                "fetched_at": _iso(chunk.fetched_at),
            }
        )
    return results
