# knowledge.asu

The Arizona State University sub-module of knowledge. It is shared: the ASU pages are crawled once for every org, and an org that turns `knowledge.asu` on searches them. It also answers live queries against ASU pages and APIs. With the [ASU sign-in](../asu_signin/README.md), agents also search clubs and events on Sun Devil Central. Other pages that need an ASU sign-in (MyASU, Canvas) are not included.

## Files

| File | Holds |
| --- | --- |
| `__init__.py` | `SUBMODULE` (`shared=True`). Its `on_enable` brings the shared pages up to date and starts the crawl of the due ones |
| `content.py` | `CONTENT`: the pages and the live queries, with the content name `asu` |
| `sources/` | Crawled ASU pages: one file for each source with its extractor, and the page list in `pages.py` |
| `queries/` | One file for each live query. `sun_devil_central.py` holds the `clubs` and `club_events` queries that need the ASU sign-in |
| `params.py` | ASU term codes, and dates and times in Arizona time |

## Pages

Turning `knowledge.asu` on (or a subscription, which is the same) adds each page as a shared crawled source with a key that starts with `asu/`. Some pages have their own extractor (library hours, read from the LibCal JSON feed behind lib.asu.edu/hours; events, courses, dining, scholarships, news, shuttles, jobs, sports). An extractor keeps each record on one line, so a chunk never splits a name from its hours or date. The `extractor` column of the source names it (`asu.<key>`).

## Live queries

Run them with `POST /api/submodules/asu/query` or the `knowledge.query` tool with `submodule` set to `asu`. The old routes `/api/asu/queries`, `/api/asu/query` and `/api/asu/sync` give the same answers.

| Source | Parameters (required are marked) |
| --- | --- |
| courses | term (required), keywords, level, days, session, open_only |
| course_catalog | keywords (required), term |
| scholarships | keywords, citizenship, applicant, focus |
| events, news | keywords |
| library_hours, jobs | none |
| study_rooms | library (required), date (required) |
| sports | sport (required) |
| sports_news | sport, keywords |
| shuttles | route |
| campus_map | place (required) |
| social_media | account, keywords |
| dining | campus (required) |
| web | query (required), time_range. Needs a SearXNG server |

courses and course_catalog read the JSON API behind the ASU class search, so they need no renderer. Pages that render with JavaScript (events, study rooms) need Firecrawl or the browser. search fills the parameters from a plain question: a course code, a term, today, tomorrow or a weekday, and a campus place by its short name (MU, SDFC). The ASU Library catalog is not a source, because its robots.txt disallows search. The `web` query needs SearXNG; its code is in [knowledge.web](../web/README.md). See [docs/modules/knowledge.md](../../../../docs/modules/knowledge.md#shared-sub-modules).

## Surface

- Switch: `knowledge.asu`. It is the org's subscription: turning it on writes the `submodule_subscriptions` row for the `knowledge.asu` row of `submodules`. Migration `c5e7a9b1d3f4` turned it on for each org that subscribed to `asu`.
- Live queries still answer for every org with knowledge on; [#459](https://github.com/asusoda/platform/issues/459) gates them on this switch.
- Extractor names stay `asu.<key>` and source keys `asu/<key>` and `asu-live/<query>-<hash>`, because `knowledge_sources` stores them.
