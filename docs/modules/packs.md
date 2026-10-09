# Packs

A pack is content for one campus or topic: public pages that Platform crawls into an org's [knowledge](./knowledge.md), live queries that agents run, [alert feeds](./alerts.md), and the school's Canvas URL for [accounts](./accounts.md). Packs are folders in [`packs/`](../../packs/README.md) of the repo. A pack holds content and settings, not new behavior, and adds no tables, routes or dashboard pages, so any org can write one. Features are [modules](../writing-a-module.md).

| Pack | Content |
| --- | --- |
| [asu](../../packs/asu/README.md) | Arizona State University: library hours, events, courses, dining, scholarships, news, shuttles, jobs, sports; the ASU Canvas URL; the ASU sign-in for Sun Devil Central ([Sign in to ASU](../integrations.md#sign-in-to-asu)) |
| [careers](../../packs/careers/__init__.py) | Alert feeds for software internships, new grad roles and hackathons |

## Add a pack to an org

Alert feeds: on the Alerts page, click **New feed** and pick the feed under **Start from**. Add a Discord webhook URL and create the feed.

Pages: on the Knowledge page of the dashboard, click **Add** next to the pack under Packs. Click **Sync** after Platform is updated to get new pages.

Sync adds each page of the pack as a crawled source of the org, with a key that starts with `<pack>/`. When you sync again, it updates URLs, categories and schedules, and turns off the `<pack>/` sources that are no longer in the pack. The crawl job then gets the pages. If the org is a knowledge publisher, the sources are public. If not, they are private.

## Routes and tools

Machine tokens only. The org is the token's org.

| Route | Scope | Does |
| --- | --- | --- |
| `GET /api/packs` | `knowledge:read` | Each pack, its pages, queries and feeds, and the number of the org's sources it owns |
| `GET /api/packs/<pack>/queries` | `knowledge:read` | The live queries and their parameters, with descriptions and allowed values |
| `POST /api/packs/<pack>/query` | `knowledge:read` | `{"source": "courses", "params": {"term": "Fall 2026"}}` returns `pack`, `source`, `url` and `text` |
| `POST /api/packs/<pack>/sync` | `knowledge:write` | Adds or updates the pack's pages as crawled sources |

`/api/asu/queries`, `/api/asu/query` and `/api/asu/sync` are the routes of the old asu module. They run the same calls for the `asu` pack.

Tools: `packs.query` (`pack`, `source`, `params`), `knowledge.packs` and `knowledge.sync_pack`. Officers use `GET /api/dashboard/<org>/knowledge/packs` and `POST /api/dashboard/<org>/knowledge/packs/<pack>/sync`.

Platform checks the parameters before it gets a page. An unknown pack or query returns 404. A bad parameter returns 422 with the values the query accepts. A failed fetch returns 502. After the answer, the `packs.index_result` job adds the result to knowledge. It uses the pack's source with the same URL if there is one, else its own `<pack>-live/<query>-<hash>` source. It does not write a result that did not change. A query with `index=False`, such as `web`, is not indexed.

## Settings

An org sets its own Firecrawl and SearXNG on the Integrations page of the dashboard ([integrations](../integrations.md)). The variables below are the deployment defaults.

| Variable | Default | Does |
| --- | --- | --- |
| `FIRECRAWL_URL` | not set | Renders JavaScript pages. If it is not set, those pages are almost empty |
| `SEARXNG_URL` | not set | The search service for the `web` query. If it is not set, that query returns 503 |
| `SEARXNG_ENGINES` | `google,brave,bing` | The engines SearXNG asks |
| `PACK_QUERY_MAX_CHARS` | 30000 | The maximum text length of a live query result. `ASU_QUERY_MAX_CHARS` still works |

## Write a pack

See [packs/README.md](../../packs/README.md).
