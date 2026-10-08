# asu

An example campus source module, for Arizona State University. It registers public ASU pages as crawled knowledge sources of an organization and answers live queries against ASU pages and APIs, then indexes what a query read into the org's knowledge.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Machine routes: list live queries, run one, sync ASU pages into the org's knowledge |
| `service.py` | `sync()`, `query()` and indexing of query results; registers the ASU extractors with knowledge |
| `queries/` | One module per live query source (courses, course catalog, dining, events, library, shuttles, sports, study rooms, web search through SearXNG, and others) |
| `queries/registry.py` | The live query sources, the parameter checks every query passes, and how a query runs |
| `queries/params.py` | Maps query parameters to search URL values, such as term codes |
| `sources/` | ASU pages crawled on a schedule: one module per source with its own extractor, plus the static page list in `pages.py` |
| `types.py` | `Source`, `QuerySource`, `QueryParam`, `QueryError` |
| `http.py` | `fetch()`, the page fetch the queries call through the knowledge fetcher, and readers for JSON, feeds and plain text |
| `text.py` | `page_text()` and `form_page_text()` around `knowledge.extract.extract_text`, and markdown line helpers |
| `settings.py` | Env settings: `ASU_QUERY_MAX_CHARS`, `SEARXNG_URL`, `SEARXNG_ENGINES` |
| `tools.py` | The `asu.query` tool |
| `jobs.py` | The indexing job |

## Surface

- Routes: `/api/asu`, no module switch. Machine tokens only: `knowledge:read` for `/queries` and `/query`, `knowledge:write` for `/sync`; the org is the token's.
- Jobs: `asu.index_result`, deferred after a live query, no schedule.
- Tools: `asu.query` (scope `knowledge:read`).
- Tables: none; writes through the knowledge tables.

## More

[docs/asu.md](../../docs/asu.md)
