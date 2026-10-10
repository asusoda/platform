# ASU

Public ASU pages and live queries (dining, library hours, events and others) that an org can add to its [knowledge](./knowledge.md). It is an example of a campus source module. Another campus adds its own module the same way. The module has no tables. Pages that need an ASU sign-in (MyASU, Canvas) are not included.

## Scheduled pages

`POST /api/asu/sync` (scope `knowledge:write`) adds each ASU page as a crawled knowledge source of the token's org, with a key that starts with `asu/`. When you run it again, it updates URLs, categories and schedules, and turns off the `asu/` sources that are no longer in the list. The crawl job then gets the pages as it does for other crawled sources.

Some pages have their own extractor (library hours, events, courses, dining, scholarships, news, shuttles, jobs, sports). An extractor keeps each record on one line, so a chunk never splits a name from its hours or date. The `extractor` column of the source names it (`asu.<key>`).

If the org is in `KNOWLEDGE_PUBLISHERS`, the sources are public. If not, they are private.

## Live queries

| Route | Scope | Does |
| --- | --- | --- |
| `GET /api/asu/queries` | `knowledge:read` | The live sources and their parameters, with descriptions and allowed values |
| `POST /api/asu/query` | `knowledge:read` | `{"source": "courses", "params": {"term": "Fall 2026"}}` returns `url` and `text` |

Agents use the `asu.query` tool for the same query. Platform checks the parameters before it gets a page. A bad parameter returns 422 with the values the source accepts. A failed fetch returns 502.

After the answer, the `asu.index_result` job adds the result to knowledge. It uses the `asu/` source with the same URL if there is one, else its own `asu-live/<query>-<hash>` source. It does not write a result that did not change.

| Source | Parameters (required are marked) |
| --- | --- |
| courses | term (required), keywords, level, days, session, open_only |
| course_catalog | keywords (required), term |
| scholarships | keywords, citizenship, applicant, focus |
| events, news | keywords |
| library_catalog | keywords (required), type |
| library_hours, jobs | none |
| study_rooms | library (required), date (required) |
| sports | sport (required) |
| sports_news | sport, keywords |
| shuttles | route |
| campus_map | place (required) |
| social_media | account, keywords |
| dining | campus (required) |
| web | query (required), time_range. Needs `SEARXNG_URL` |

## Settings

| Variable | Default | Does |
| --- | --- | --- |
| `FIRECRAWL_URL` | not set | Renders JavaScript pages (class search, events). If it is not set, those pages are almost empty |
| `SEARXNG_URL` | not set | The search service for the `web` query. If it is not set, that query returns 503 |
| `SEARXNG_ENGINES` | `google,brave,bing` | The engines SearXNG asks |
| `ASU_QUERY_MAX_CHARS` | 30000 | The maximum text length of a live query result |
