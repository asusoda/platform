# asu

The Arizona State University pack. It adds public ASU pages to an org's knowledge as crawled sources, and answers live queries against ASU pages and APIs. Pages that need an ASU sign-in (MyASU, Canvas) are not included.

## Files

| File | Holds |
| --- | --- |
| `__init__.py` | `PACK`: the pages and the live queries |
| `sources/` | Crawled ASU pages: one file for each source with its extractor, and the page list in `pages.py` |
| `queries/` | One file for each live query |
| `params.py` | ASU term codes, and dates and times in Arizona time |

## Pages

Sync adds each page as a crawled source with a key that starts with `asu/`. Some pages have their own extractor (library hours, events, courses, dining, scholarships, news, shuttles, jobs, sports). An extractor keeps each record on one line, so a chunk never splits a name from its hours or date. The `extractor` column of the source names it (`asu.<key>`).

## Live queries

Run them with `POST /api/packs/asu/query` or the `packs.query` tool with `pack` set to `asu`. The old routes `/api/asu/queries`, `/api/asu/query` and `/api/asu/sync` give the same answers.

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
| web | query (required), time_range. Needs a SearXNG server |

Pages that render with JavaScript (class search, events) need Firecrawl. The `web` query needs SearXNG. See [docs/modules/packs.md](../../docs/modules/packs.md).
