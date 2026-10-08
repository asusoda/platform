# Knowledge module

Sources of text that agents search: pages a scraper fetched, handbooks, FAQs. Writers send a
source as chunks; the platform stores and searches them but never fetches pages itself. The
columns and the search follow SparkyAI's retrieval index, so its scraper can write here and its
engine can search here instead of keeping its own tables.

## Who can see what

- Writers and searchers call with a machine token holding `knowledge:write` and/or
  `knowledge:read`. The org is the token's.
- Search covers the caller's org plus public sources. Only orgs listed in `KNOWLEDGE_PUBLISHERS`
  (org prefixes, comma separated, set by whoever runs the platform) may write public sources,
  because a public source shows up in every org's results.
- Listing, reading and deleting sources covers the caller's org only.

## Routes

All under `/api/knowledge`.

| Method and path | Scope | Does |
|---|---|---|
| `GET /sources?category=` | read | The org's sources with their current version |
| `GET /sources/<key>` | read | One source |
| `PUT /sources/<key>` | write | Create or replace. 201 when the content changed, 200 when it did not |
| `DELETE /sources/<key>` | write | Delete the source, its versions and chunks |
| `POST /search` | read | Ranked passages. Not written to the audit log |

The key is the writer's stable name for the source (letters, digits, `._:/-`, up to 255).

`PUT` body:

```json
{
  "category": "library",
  "title": "Hayden Library hours",
  "url": "https://lib.asu.edu/hours",
  "public": false,
  "content_hash": "optional, computed from the chunks when missing",
  "embedding_model": "required when chunks carry embeddings",
  "chunks": [
    {"ordinal": 0, "content": "...", "embedding": [1024 numbers], "level": 0, "parent_ordinal": 2}
  ]
}
```

- A source is replaced whole. When `content_hash` matches the current version, only the title,
  URL, category and public flag are updated. Otherwise a new version replaces the old one.
- `level` 0 is page text; 1 and up are summaries of the rows below them (`parent_ordinal` points
  from a row to its summary). Up to 5000 chunks of up to 20000 characters each.
- Either every chunk has an `embedding` (1024 numbers) or none does. With none and an embedder
  configured, the platform embeds them. With none and no embedder, the source is text only.

`POST /search` body: `query`, optional `category`, `top_k` (1 to 50, default 8), `window`
(0 to 5, default 0), and optionally `embedding` plus `embedding_model` to search with the
caller's own query vector. Each result has `chunk_id`, `source_key`, `title`, `url`, `category`,
`public`, `content`, `score`, `fetched_at`. `dense` in the response says whether the vector leg ran.

The same search is the `knowledge.search` tool over MCP and `/api/tools`.

## How search works

1. Vector leg: the nearest chunks to the query vector, among chunks embedded with the same
   model, dropping those further than `KNOWLEDGE_MAX_DISTANCE` (cosine distance, default 0.6).
2. Text leg: Postgres full-text search (`websearch_to_tsquery`, ranked by `ts_rank_cd`). On
   SQLite, a count of shared words.
3. The two lists are fused with reciprocal rank fusion (k = 60).
4. A row whose summary already ranked higher is dropped.
5. With `window`, a page text hit carries that many neighboring rows on each side.

If the embedder fails during a search, the search runs on text alone. If it fails during a write,
the write fails with 502.

## Storage

Tables `knowledge_sources`, `knowledge_versions`, `knowledge_chunks`. On Postgres with pgvector
the embedding column is `vector(1024)` with an HNSW index, and the text has a GIN full-text index.
The migration checks whether pgvector is installed: without it the column stays text and the
vector leg runs in Python, which is fine for small indexes. The compose `postgres` service and
CI use the `pgvector/pgvector:pg16` image. On SQLite both legs run in Python.

## Configuration

| Variable | Default | Does |
|---|---|---|
| `EMBEDDINGS_URL` | unset | OpenAI-compatible base URL (`.../v1`). Unset means no embedder |
| `EMBEDDINGS_MODEL` | `default` | Model name sent to the endpoint and stored on each version |
| `EMBEDDINGS_API_KEY` | unset | Bearer key for the endpoint |
| `EMBEDDINGS_QUERY_PREFIX` | empty | Put before queries, for models that embed queries differently |
| `KNOWLEDGE_MAX_DISTANCE` | 0.6 | Vector matches further than this are dropped |
| `KNOWLEDGE_PUBLISHERS` | empty | Org prefixes allowed to write public sources |
