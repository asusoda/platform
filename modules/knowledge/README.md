# knowledge

Holds an organization's knowledge sources and searches them. Writers send a source as chunks, or the platform crawls a URL on a schedule; search fuses a vector ranking and a text ranking over the org's sources plus public ones.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Machine routes: sources, search, crawled source registration, crawl runs |
| `service.py` | Sources, versions, chunks and hybrid search; declares the `knowledge:read` and `knowledge:write` scopes; only orgs in `KNOWLEDGE_PUBLISHERS` write public sources |
| `crawl.py` | Scheduled crawls: fetch, extract, chunk, embed, index; refuses a run whose text shrank below half of the last version |
| `fetch.py` | Fetching with robots.txt, per-host pacing and public addresses only; through Firecrawl when `FIRECRAWL_URL` is set |
| `extract.py` | HTML to text, and text to chunks |
| `extractors.py` | Named extractors that other modules register for their sources |
| `embedder.py` | OpenAI-compatible embeddings client, configured by `EMBEDDINGS_URL` |
| `models.py` | Sources, versions, chunks; pgvector on Postgres, JSON vectors on SQLite |
| `tools.py` | The `knowledge.search` tool |
| `jobs.py` | The crawl jobs |

## Surface

- Routes: `/api/knowledge`, no module switch. Machine tokens only, with `knowledge:read` or `knowledge:write`; the org is the token's.
- Jobs: `knowledge.crawl_due`, cron `*/10 * * * *`; `knowledge.crawl_source`, on request.
- Tools: `knowledge.search` (scope `knowledge:read`).
- Tables: `knowledge_sources`, `knowledge_versions`, `knowledge_chunks`.

## Depends on

`core.audit_http`, `core.errors`, `core.jobs`, `core.tools`, `core.logging_config`, `core.base`; `modules.auth` (routes, scopes); `shared`.

## More

[docs/knowledge.md](../../docs/knowledge.md)
