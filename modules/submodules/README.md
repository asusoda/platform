# submodules

Loads the submodules in the `submodules/` folder and keeps each org's subscriptions. A submodule is a domain, such as a campus or careers: content, not a feature. The dashboard calls submodules shared content. An org subscribes to it once, and each module that reads it gets its part:

- knowledge searches its pages, which are the submodule's own sources: crawled and embedded once by the deployment, with no org;
- [feeds](../feeds/README.md) offers its feeds as presets;
- agents run its live queries (`knowledge.query`, or `search`, which reads stored pages first), whose results become sources of the org.

See [submodules/README.md](../../submodules/README.md) to write one.

## Files

| File | Holds |
| --- | --- |
| `catalog.py` | Loads each folder in `submodules/` once per process and registers its extractors with knowledge |
| `models.py` | `Submodule` (one row for each submodule) and `SubmoduleSubscription` |
| `service.py` | `list_submodules()`, `subscribe()`, `unsubscribe()`, `sync_shared()` (the shared sources of a submodule), `sync()` (the older name of `subscribe()`), `overview()` for the superadmin, the parts of each submodule with who pays for each (`_parts()`), `query()` and the indexing of query results; declares `submodules:read`, `submodules:manage` and the `submodules.subscriptions` limit |
| `api.py`, `tools.py` | Machine routes to list submodules, subscribe and end a subscription, and list and run live queries; the older sync routes and `/api/asu` routes; the `submodules.*` tools |
| `types.py` | `Submodule`, `Source`, `QuerySource`, `QueryParam`, `Feed`, `QueryError` |
| `signins.py` | Sign-ins that a live query reads pages behind (`signin` on a `QuerySource`), such as `asu` |
| `queries.py`, `params.py` | Parameter checks and the run of one live query; helpers that map parameters to URL values |
| `find.py`, `fill.py` | The `search` tool: stored pages, then the named live query, then `web`; the parameters of a live query filled from one plain query |
| `http.py`, `text.py` | Page, JSON and feed fetches; text and Markdown helpers for extractors |
| `search.py`, `web.py` | `SUBMODULE_QUERY_MAX_CHARS`; the SearXNG integration; `query_scope()` sets the org's SearXNG and Firecrawl; the `web` live query that a submodule can add |
| `jobs.py` | The indexing job |

## Surface

- Routes: `/api/submodules`, and `/api/asu` for clients of the old asu module. Machine tokens only. `PUT` and `DELETE /<name>/subscription` need `submodules:manage` and no module switch. Listing and live queries need `knowledge:read`; the older `POST /<name>/sync` needs `knowledge:write` and subscribes. Officers use `/api/dashboard/<org>/submodules` and `/api/dashboard/<org>/submodules/<name>/subscription`; the superadmin uses `GET /api/superadmin/submodules`.
- Jobs: `submodules.index_result`, started after a live query.
- Tools: `modules.submodules` (scope `submodules:read`); `modules.subscribe` (confirm) and `modules.unsubscribe` (confirm) (scope `submodules:manage`); `knowledge.query` and `search` (scope `knowledge:read`). `knowledge.submodules` and `knowledge.sync_submodule` in the knowledge module do the same as `modules.submodules` and `modules.subscribe`. Tools marked confirm run only with `confirm=true`.
- Limits: `submodules.subscriptions` (default 20). A submodule's shared pages count against no org.
- Tables: `submodules`, `submodule_subscriptions`. A submodule's pages are rows in `knowledge_sources` and `knowledge_chunks` with `submodule_id` set and no `organization_id`. Migration `657f276f6993` keeps one org's copy of each submodule as its shared sources, subscribes each org that had a copy or a feed from its presets, and deletes the other copies.

See [docs/modules/submodules.md](../../docs/modules/submodules.md).
