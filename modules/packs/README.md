# packs

Loads the packs in the `packs/` folder. Adds a pack's pages to an org's knowledge as crawled sources and runs the pack's live queries. The alerts module reads pack feeds and the accounts module reads `canvas_url`. A pack is content for one campus or topic, not a feature. See [packs/README.md](../../packs/README.md) to write one.

## Files

| File | Holds |
| --- | --- |
| `catalog.py` | Loads each folder in `packs/` once per process and registers its extractors with knowledge |
| `service.py` | `list_packs()`, `sync()`, `query()` and the indexing of query results |
| `api.py`, `tools.py` | Machine routes to list packs, list and run live queries and sync pages; the old `/api/asu` routes; the `packs.query` tool |
| `types.py` | `Pack`, `Source`, `QuerySource`, `QueryParam`, `Feed`, `QueryError` |
| `queries.py`, `params.py` | Parameter checks and the run of one live query; helpers that map parameters to URL values |
| `http.py`, `text.py` | Page, JSON and feed fetches; text and Markdown helpers for extractors |
| `search.py`, `web.py` | `PACK_QUERY_MAX_CHARS`; the SearXNG integration; `query_scope()` sets the org's SearXNG and Firecrawl; the `web` live query that a pack can add |
| `jobs.py` | The indexing job |

## Surface

- Routes: `/api/packs`, and `/api/asu` for clients of the old asu module. Machine tokens only: `knowledge:read` to list and query, `knowledge:write` to sync.
- Jobs: `packs.index_result`, started after a live query.
- Tools: `packs.query` (scope `knowledge:read`). `knowledge.packs` and `knowledge.sync_pack` are in the knowledge module.
- Tables: none. It writes to the knowledge tables.

See [docs/modules/packs.md](../../docs/modules/packs.md).
