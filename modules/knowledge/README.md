# knowledge

Keeps an org's knowledge sources and searches them. Writers send a source as chunks, officers upload documents, or Platform crawls a URL on a schedule. Search merges a vector ranking and a text ranking over the org's sources, the public ones, and the shared pages of the sub-modules the org has on.

Sub-modules:

- [knowledge.asu](submodules/asu/README.md): shared ASU pages and live queries.
- [knowledge.web](submodules/web/README.md): web search through SearXNG.
- [knowledge.asu_signin](submodules/asu_signin/README.md): an officer's ASU sign-in for Sun Devil Central.

## Files

| File | Holds |
| --- | --- |
| `api.py`, `tools.py` | Machine routes for sources, search and crawls, the shared sub-modules (`/api/submodules`) and the old asu routes (`/api/asu`); the knowledge tools, the shared sub-module tools and the `search` tool |
| `shared.py` | Shared sub-modules: the list, subscribe and unsubscribe (through the sub-module switch), the sync of shared pages, the superadmin overview, live queries and the indexing of their results; declares `submodules:read` and `submodules:manage` |
| `content/` | Content helpers for crawled pages and live queries: `types.py` (`Content`, `Source`, `QuerySource`, `QueryParam`, `QueryError`), `catalog.py` (the `content.py` of each knowledge sub-module, and their extractors), `queries.py`, `params.py`, `fill.py`, `find.py` (the `search` tool), `signins.py`, `http.py`, `text.py`, `search.py` (the SearXNG integration and `query_scope()`) |
| `service.py` | Sources, versions and chunks; declares `knowledge:read` and `knowledge:write`; checks publishers (superadmin flag or `KNOWLEDGE_PUBLISHERS`) |
| `search.py` | Hybrid search with reciprocal rank fusion |
| `fts.py` | The SQLite FTS5 index of chunk text and its triggers, for the text ranking on SQLite |
| `crawl.py` | Crawls: fetch, extract, chunk, embed, index; `queue` starts the crawl job for one source |
| `discover.py` | Pages agents read, saved as crawled sources |
| `fetch.py` | Fetches with robots.txt, per-host pauses and public addresses only; registers the Firecrawl integration and uses the org's Firecrawl |
| `render.py` | Renders a thin page again in the shared browser (`BROWSER_URL`), in a new context for each page, with the request guard of `core/browser.py`; declares `knowledge.renders_per_day` |
| `extract.py` | HTML to text, text to chunks, and the extractors that other modules register |
| `documents.py` | Uploaded files (text, Markdown, HTML, PDF, Word) indexed as sources |
| `settings.py` | Per-org passage size and search settings, kept in the org config |
| `runs.py` | The log of crawls and uploads |
| `reembed.py` | Passage counts by embedding model; embeds passages of another model again from their stored text |
| `embedder.py` | The OpenAI-compatible embeddings client; registers the Embeddings integration; `for_org()` picks the org's service or the `.env` default, and the OpenRouter key for an OpenRouter URL with no key |
| `models.py`, `jobs.py` | Sources, versions, chunks (pgvector on Postgres), runs; the crawl, reindex and live result jobs |

## Surface

- Routes: `/api/knowledge`, `/api/submodules` and `/api/asu`. Machine tokens only, with `knowledge:read`, `knowledge:write` or `knowledge:discover` (`POST /discovered` only). `PUT` and `DELETE /api/submodules/<name>/subscription` need `submodules:manage` and no module switch. `<name>` is a sub-module key (`knowledge.asu`), its short name (`asu`), or `careers` for both feeds sub-modules. The officer routes for sources, source text, crawls, uploads, settings, runs, shared sub-modules and reindex are in `modules/dashboard/api.py`.
- Jobs: `knowledge.crawl_due`, schedule `*/10 * * * *`; `knowledge.crawl_source`, `knowledge.reindex` and `knowledge.reembed`, on request. Saving the Embeddings integration starts `knowledge.reembed`. `submodules.index_result`, after a live query.
- Tools: `knowledge.search`, `knowledge.sources`, `knowledge.read_source`, `knowledge.submodules`, `knowledge.settings`, `knowledge.embeddings`, `knowledge.runs`, `knowledge.query`, `search` (scope `knowledge:read`); `knowledge.add_document`, `knowledge.delete_source` (confirm), `knowledge.set_crawl`, `knowledge.crawl_now`, `knowledge.sync_submodule`, `knowledge.update_settings`, `knowledge.reindex` (confirm), `knowledge.reembed` (confirm) (scope `knowledge:write`); `modules.submodules` (scope `submodules:read`, no switch); `modules.subscribe` (confirm) and `modules.unsubscribe` (confirm) (scope `submodules:manage`, no switch). Tools marked confirm run only with `confirm=true`.
- Webhook events: `knowledge.crawl_failed`, from `runs.record()`. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `knowledge_sources`, `knowledge_versions`, `knowledge_chunks`, `knowledge_runs`.
- On SQLite the text ranking reads the FTS5 table `knowledge_chunks_fts`, which triggers keep in step with `knowledge_chunks`. Without it, the text ranking scans every chunk in Python. A batch migration that rebuilds `knowledge_chunks` drops the triggers, so it must call `fts.install` again.
- Search reads the org's own sources, public sources, and the shared sources of the sub-modules it has on (`submodule_id`, no org; the subscription rows of `core/submodules.py`). Shared sources are crawled with the deployment's embedder, Firecrawl and chunk settings, and are not in an org's run log.
- Limits: `knowledge.discovered_per_day` (`discover.py`), `knowledge.sources` and `knowledge.passages` (`service.py`, shared sources not counted), `knowledge.uploads_per_day` and `knowledge.jobs_per_day` (`service.py`), `submodules.subscriptions` (`core/submodules.py`, default 20), `knowledge.embeddings_per_day` (`embedder.py`, each text that an org's embedder embeds), `knowledge.renders_per_day` (`render.py`, each page an org renders in the browser; 0 by default, so an org renders only after the superadmin raises it). `knowledge.reindex` and `knowledge.reembed` run once at a time for each org, `knowledge.crawl_source` once for each source. The crawl of due sources takes one source of each org in turn. See [docs/limits.md](../../docs/limits.md).

See [docs/modules/knowledge.md](../../docs/modules/knowledge.md).
