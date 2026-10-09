# knowledge

Keeps an org's knowledge sources and searches them. Writers send a source as chunks, officers upload documents, or Platform crawls a URL on a schedule. Search merges a vector ranking and a text ranking over the org's sources and the public ones.

## Files

| File | Holds |
| --- | --- |
| `api.py`, `tools.py` | Machine routes for sources, search and crawls; the `knowledge.search` tool |
| `service.py` | Sources, versions and chunks; declares `knowledge:read` and `knowledge:write`; checks publishers (superadmin flag or `KNOWLEDGE_PUBLISHERS`) |
| `search.py` | Hybrid search with reciprocal rank fusion |
| `crawl.py` | Crawls: fetch, extract, chunk, embed, index; `queue` starts the crawl job for one source |
| `fetch.py` | Fetches with robots.txt, per-host pauses and public addresses only; registers the Firecrawl integration and uses the org's Firecrawl |
| `extract.py` | HTML to text, text to chunks, and the extractors that other modules register |
| `documents.py` | Uploaded files (text, Markdown, HTML, PDF, Word) indexed as sources |
| `settings.py` | Per-org passage size and search settings, kept in the org config |
| `runs.py` | The log of crawls and uploads |
| `embedder.py` | The OpenAI-compatible embeddings client; registers the Embeddings integration; `for_org()` picks the org's service or the `.env` default |
| `models.py`, `jobs.py` | Sources, versions, chunks (pgvector on Postgres), runs; the crawl and reindex jobs |

## Surface

- Routes: `/api/knowledge`. Machine tokens only, with `knowledge:read` or `knowledge:write`. The officer routes for sources, crawls, uploads, settings, runs, packs and reindex are in `modules/dashboard/api.py`.
- Jobs: `knowledge.crawl_due`, schedule `*/10 * * * *`; `knowledge.crawl_source` and `knowledge.reindex`, on request.
- Tools: `knowledge.search`, `knowledge.sources`, `knowledge.packs`, `knowledge.settings`, `knowledge.runs` (scope `knowledge:read`); `knowledge.add_document`, `knowledge.delete_source` (confirm), `knowledge.set_crawl`, `knowledge.crawl_now`, `knowledge.sync_pack`, `knowledge.update_settings`, `knowledge.reindex` (confirm) (scope `knowledge:write`). Tools marked confirm run only with `confirm=true`.
- Webhook events: `knowledge.crawl_failed`, from `runs.record()`. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `knowledge_sources`, `knowledge_versions`, `knowledge_chunks`, `knowledge_runs`.

See [docs/modules/knowledge.md](../../docs/modules/knowledge.md).
