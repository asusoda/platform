"""SQLite full-text index of knowledge chunk text. No Flask here.

Postgres searches text with its GIN index. On SQLite an FTS5 table keeps a copy of each chunk's text,
filled by triggers, so the text leg of search runs in SQL. A batch migration that rebuilds
knowledge_chunks drops the triggers; search then falls back to Python until install runs again.
"""

from sqlalchemy import text

TABLE = "knowledge_chunks_fts"
TRIGGER = "knowledge_chunks_fts_insert"

DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(chunk_id UNINDEXED, content, tokenize='unicode61')",
    "CREATE TRIGGER IF NOT EXISTS knowledge_chunks_fts_insert AFTER INSERT ON knowledge_chunks BEGIN"
    " INSERT INTO knowledge_chunks_fts(rowid, chunk_id, content) VALUES (new.rowid, new.id, new.content); END",
    "CREATE TRIGGER IF NOT EXISTS knowledge_chunks_fts_delete AFTER DELETE ON knowledge_chunks BEGIN"
    " DELETE FROM knowledge_chunks_fts WHERE rowid = old.rowid AND chunk_id = old.id; END",
    "CREATE TRIGGER IF NOT EXISTS knowledge_chunks_fts_update AFTER UPDATE OF content ON knowledge_chunks BEGIN"
    " DELETE FROM knowledge_chunks_fts WHERE rowid = old.rowid AND chunk_id = old.id;"
    " INSERT INTO knowledge_chunks_fts(rowid, chunk_id, content) VALUES (new.rowid, new.id, new.content); END",
)
FILL = "INSERT INTO knowledge_chunks_fts(rowid, chunk_id, content) SELECT rowid, id, content FROM knowledge_chunks"
DROP = (
    "DROP TRIGGER IF EXISTS knowledge_chunks_fts_update",
    "DROP TRIGGER IF EXISTS knowledge_chunks_fts_delete",
    "DROP TRIGGER IF EXISTS knowledge_chunks_fts_insert",
    "DROP TABLE IF EXISTS knowledge_chunks_fts",
)


def install(connection) -> None:
    """Creates the index and its triggers on a SQLite connection and fills it from the chunks."""
    for statement in (*DROP, *DDL, FILL):
        connection.exec_driver_sql(statement)


def available(db) -> bool:
    """Whether the index and its insert trigger exist, so the index matches the chunks."""
    found = db.execute(
        text("SELECT count(*) FROM sqlite_master WHERE name IN (:table, :trigger)"),
        {"table": TABLE, "trigger": TRIGGER},
    ).scalar()
    return found == 2


def match(terms: set[str]) -> str:
    """An FTS5 query that matches any of the terms. Terms hold only letters and digits."""
    return " OR ".join(f'"{term}"' for term in sorted(terms))
