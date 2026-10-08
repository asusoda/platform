"""Sources, their versions, and the chunks search runs over.

On Postgres, chunk embeddings are pgvector columns with an HNSW index and the text has a full-text
GIN index (both created in the migration, named pg_*). On SQLite, embeddings are JSON text and
search runs in Python, which is enough for development and tests.
"""

import json
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import TypeDecorator, UserDefinedType

from core.db import Base
from core.time import utcnow

DIMENSIONS = 1024  # Qwen3-Embedding-0.6B


def _uuid() -> str:
    return str(uuid.uuid4())


class _PgVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def get_col_spec(self, **kw) -> str:
        return f"vector({self.dimensions})"


class Embedding(TypeDecorator):
    """A float vector: pgvector on Postgres, JSON text elsewhere. Both use the [a,b,c] literal."""

    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = DIMENSIONS):
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PgVector(self.dimensions))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return "[" + ",".join(repr(float(x)) for x in value) + "]"

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return [float(x) for x in json.loads(value)]


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    key = Column(String(255), nullable=False)  # stable name the writer chooses
    url = Column(Text, nullable=True)
    title = Column(String(500), nullable=True)
    category = Column(String(100), nullable=False)
    public = Column(Boolean, nullable=False, default=False)  # readable by every org
    current_version_id = Column(String(36), nullable=True)
    # Crawled sources: the platform fetches url on this schedule. None means a writer sends chunks.
    fetch_every_hours = Column(Integer, nullable=True)
    extractor = Column(String(100), nullable=True)  # a name in modules/knowledge/extractors.py
    enabled = Column(Boolean, nullable=False, default=True)
    last_attempt_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_knowledge_source_key"),)


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    source_id = Column(String(36), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False)
    embedding_model = Column(String(200), nullable=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    text_chars = Column(Integer, nullable=True)  # extracted text length, for crawled sources
    fetched_at = Column(DateTime, nullable=False, default=utcnow)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    source_id = Column(String(36), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(String(36), ForeignKey("knowledge_versions.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(100), nullable=False)
    public = Column(Boolean, nullable=False, default=False)
    ordinal = Column(Integer, nullable=False)
    level = Column(Integer, nullable=False, default=0)  # 0 page text, 1+ summaries of rows below
    parent_ordinal = Column(Integer, nullable=True)  # the summary row that covers this one
    content = Column(Text, nullable=False)
    embedding = Column(Embedding(), nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("version_id", "ordinal", name="uq_knowledge_chunk_ordinal"),
        Index("ix_knowledge_chunks_scope", "organization_id", "category", "level"),
        Index("ix_knowledge_chunks_public", "public", "category"),
    )
