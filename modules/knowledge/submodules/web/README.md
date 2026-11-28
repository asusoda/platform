# knowledge.web

Web search through SearXNG: titles, links and snippets from Google, Brave and Bing. The org sets its own SearXNG on the Integrations tab of Explore, else `SEARXNG_URL` gives the deployment's.

## Files

| File | Holds |
| --- | --- |
| `__init__.py` | `SUBMODULE` |
| `query.py` | The `web` live query. The asu content lists it in its queries, and `search` falls back to it |
| `tools.py` | The `knowledge.web_search` tool and the `web:read` scope |

## Surface

- Tools: `knowledge.web_search` (scope `web:read`), shown when the org or the deployment has a SearXNG.
- Switch: `knowledge.web` gates the tool. Migration `c5e7a9b1d3f4` gave it the `integrations` value, because the tool belonged to integrations. For one release, `LEGACY_PARENTS` in `modules/organizations/service.py` keeps it on while knowledge is off and integrations is on, so those orgs keep the tool.
- The `web` query in `search` and `knowledge.query` still answers for every org with knowledge on; [#459](https://github.com/asusoda/platform/issues/459) moves it under this switch.
