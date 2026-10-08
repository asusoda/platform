# Knowledge

Sources of text that agents search, such as web pages, handbooks and FAQs. A client writes a source as chunks, or Platform crawls a URL on a schedule.

## Access

- Writers and searchers use a machine token with `knowledge:write`, `knowledge:read` or both. The org is the org of the token.
- Search covers the caller's org and the public sources. A public source shows in the results of every org. Thus only the orgs in `KNOWLEDGE_PUBLISHERS` (org prefixes, comma-separated) can write one.
- List, read and delete cover only the caller's org.
- Officers manage crawls and test search on the Knowledge page of the dashboard, with no token.

## Routes

All routes are under `/api/knowledge`.

| Route | Scope | Does |
| --- | --- | --- |
| `GET /sources?category=` | read | The org's sources and their current version |
| `GET /sources/<key>` | read | One source |
| `PUT /sources/<key>` | write | Creates or replaces a source. 201 if the content changed, 200 if not |
| `DELETE /sources/<key>` | write | Deletes the source, its versions and its chunks |
| `POST /search` | read | Ranked passages. The audit log does not record searches |
| `PUT /crawls/<key>` | write | A crawled source: `url`, `category`, `fetch_every_hours` (1 to 720, default 24), `title`, `public`, `enabled` |
| `POST /crawls/run` | write | `{"key": ..., "force": false}`. Starts a crawl now. 202 |

The key is the writer's fixed name for the source: letters, digits and `._:/-`, 255 characters or fewer.

```json
{
  "category": "library",
  "title": "Library hours",
  "url": "https://example.edu/library/hours",
  "public": false,
  "content_hash": "optional; computed from the chunks if missing",
  "embedding_model": "required if the chunks have embeddings",
  "chunks": [
    {"ordinal": 0, "content": "...", "embedding": [1024 numbers], "level": 0, "parent_ordinal": 2}
  ]
}
```

- A `PUT` replaces the whole source. If `content_hash` is the hash of the current version, only the title, URL, category and public flag change.
- `level` 0 is page text. Levels 1 and higher are summaries of the rows below them. `parent_ordinal` points from a row to its summary. A source has up to 5000 chunks of up to 20000 characters.
- All chunks have an `embedding` (1024 numbers), or none do. If none do and an embedder is set, Platform makes the embeddings. If there is no embedder, the source is text only.

The `POST /search` body has `query`, and optional `category`, `top_k` (1 to 50, default 8), `window` (0 to 5, default 0), and `embedding` with `embedding_model` to search with the caller's own vector. Each result has `chunk_id`, `source_key`, `title`, `url`, `category`, `public`, `content`, `score` and `fetched_at`. `dense` in the response shows if the vector search ran. The `knowledge.search` tool runs the same search.

## Crawls

The `knowledge.crawl_due` job runs every 10 minutes. It crawls up to `KNOWLEDGE_CRAWL_BATCH` sources that are due, with `KNOWLEDGE_CRAWL_GAP_SECONDS` between fetches to the same host. Each crawl does these steps:

1. Checks that the URL is http or https and resolves only to public addresses. It follows redirects one at a time and checks each one. Thus a source cannot point Platform at its own network.
2. Reads robots.txt with `KNOWLEDGE_USER_AGENT` and skips pages that it does not allow.
3. Gets the page through Firecrawl if `FIRECRAWL_URL` is set, else with a GET of up to 10 MB.
4. Stops if the page hash did not change, unless `force` is set.
5. Removes navigation, headers, footers, forms and scripts. Splits the text into chunks of `KNOWLEDGE_CHUNK_CHARS` characters with the page title on each, makes the embeddings and replaces the source's version.
6. Refuses the new text if it is less than half of the last version (when that was 500 characters or more), so a broken page cannot remove a good index. `force` accepts it.

A source's `crawl` field shows its schedule, `last_attempt_at` and `last_error`.

## Search

1. Vector search: the chunks nearest to the query vector, of the same embedding model. It drops chunks farther than `KNOWLEDGE_MAX_DISTANCE` (cosine distance).
2. Text search: Postgres full text search (`websearch_to_tsquery`, ranked by `ts_rank_cd`). On SQLite, a count of shared words.
3. Reciprocal rank fusion (k = 60) merges the two lists.
4. A row is dropped if its summary has a higher rank.
5. With `window`, a page text result also has that number of rows on each side.

If the embedder fails during a search, the search uses text only. If it fails during a write, the write returns 502.

On Postgres with pgvector, the embedding column is `vector(1024)` with an HNSW index, and the text has a GIN index. If pgvector is not installed, the migration keeps the column as text and the vector search runs in Python. On SQLite both searches run in Python.

## Settings

| Variable | Default | Does |
| --- | --- | --- |
| `EMBEDDINGS_URL` | not set | An OpenAI-compatible base URL (`.../v1`). If it is not set, there is no embedder |
| `EMBEDDINGS_MODEL` | `default` | The model name sent to the URL and kept on each version |
| `EMBEDDINGS_API_KEY` | not set | The bearer token for the URL |
| `EMBEDDINGS_QUERY_PREFIX` | empty | Text put before queries, for models that need it |
| `KNOWLEDGE_MAX_DISTANCE` | 0.6 | Vector results farther than this are dropped |
| `KNOWLEDGE_PUBLISHERS` | empty | Org prefixes that can write public sources |
| `KNOWLEDGE_CHUNK_CHARS` | 300 | The chunk size for crawled pages |
| `KNOWLEDGE_CRAWL_BATCH` | 20 | Sources crawled in each run of the job |
| `KNOWLEDGE_CRAWL_GAP_SECONDS` | 2 | The time between fetches to one host |
| `KNOWLEDGE_USER_AGENT` | `PlatformKnowledgeBot/1.0` | Sent with fetches and matched against robots.txt |
| `FIRECRAWL_URL`, `FIRECRAWL_API_KEY` | not set | A self-hosted Firecrawl for JavaScript pages |
