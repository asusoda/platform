# asu

An example campus source module, for Arizona State University. It adds public ASU pages to an org's knowledge as crawled sources, and answers live queries against ASU pages and APIs.

## Files

| File | Holds |
| --- | --- |
| `api.py`, `tools.py` | Machine routes to list and run live queries and to sync ASU pages; the `asu.query` tool |
| `service.py` | `sync()`, `query()` and the indexing of query results; registers the ASU extractors with knowledge |
| `queries/` | One file for each live query source; `registry.py` checks parameters and runs a query; `params.py` maps parameters to URL values |
| `sources/` | Crawled ASU pages: one file for each source with its extractor, and the page list in `pages.py` |
| `types.py`, `http.py`, `text.py` | `Source`, `QuerySource`, `QueryError`; page fetches and readers; text and markdown helpers |
| `settings.py` | `ASU_QUERY_MAX_CHARS`, `SEARXNG_URL`, `SEARXNG_ENGINES` |
| `jobs.py` | The indexing job |

## Surface

- Routes: `/api/asu`. Machine tokens only: `knowledge:read` for `/queries` and `/query`, `knowledge:write` for `/sync`.
- Jobs: `asu.index_result`, started after a live query.
- Tools: `asu.query` (scope `knowledge:read`).
- Tables: none. It writes to the knowledge tables.

See [docs/modules/asu.md](../../docs/modules/asu.md).
