# ASU sources

The ASU pages and live queries from SparkyAI's scraper, ported into the platform so any org can
index them. The module only feeds the knowledge module (docs/knowledge.md); it has no tables of
its own. Pages behind an ASU sign-in (MyASU, Canvas) are not ported.

## Scheduled pages

`POST /api/asu/sync` (scope `knowledge:write`) registers every ASU page as a crawled knowledge
source of the token's org, under keys starting with `asu/`. Running it again updates URLs,
categories and schedules, and disables `asu/` sources no longer in the list. The crawl job then
fetches them like any other crawled source.

Some pages have their own extractor (library hours, events, courses, dining, scholarships, news,
shuttles, jobs, sports) that keeps each record on one line, so a chunk never splits a name from
its hours or date. The source's `extractor` column names it (`asu.<key>`).

The sources are public when the org is listed in `KNOWLEDGE_PUBLISHERS`, private otherwise.

## Live queries

| Method and path | Scope | Does |
|---|---|---|
| `GET /api/asu/queries` | `knowledge:read` | The live sources and the parameters each takes |
| `POST /api/asu/query` | `knowledge:read` | `{"source": "courses", "params": {"term": "Fall 2026"}}` returns `url` and `text` |

Agents call the same through the `asu.query` tool. Parameters are checked before anything is
fetched; a bad one answers 422 with what the source accepts. A failed fetch answers 502.

After answering, the result is queued as the `asu.index_result` job. It is indexed under the
`asu/` source with the same URL when there is one, else under its own `asu-live/<query>-<hash>`
source. An unchanged result is not written again.

| Source | Params (required marked) |
|---|---|
| courses | term (required), keywords, level, days, session, open_only |
| course_catalog | keywords (required), term |
| scholarships | keywords, citizenship, applicant, focus |
| events | keywords |
| news | keywords |
| library_catalog | keywords (required), type |
| library_hours | none |
| study_rooms | library (required), date (required) |
| sports | sport (required) |
| sports_news | sport, keywords |
| shuttles | route |
| campus_map | place (required) |
| social_media | account, keywords |
| dining | campus (required) |
| jobs | none |
| web | query (required), time_range; needs `SEARXNG_URL` |

`GET /api/asu/queries` is the full list with descriptions and allowed values.

## Settings

| Variable | Default | Does |
|---|---|---|
| `FIRECRAWL_URL` | unset | Renders JavaScript pages (class search, events). Unset, those pages come back mostly empty |
| `SEARXNG_URL` | unset | Search backend for the `web` query. Unset, that query answers 503 |
| `SEARXNG_ENGINES` | google,brave,bing | Engines SearXNG asks |
| `ASU_QUERY_MAX_CHARS` | 30000 | Longest text a live query returns |
