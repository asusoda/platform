# Modules

One folder for each module. Each folder has a `README.md` with its files and its surface: routes, jobs, tools and tables. [docs/writing-a-module.md](../docs/writing-a-module.md) gives the rules and the places to register a new module.

The folders are not nested. `CATEGORIES` in `manifest.py` groups the modules below in the same sections as the sidebar of the dashboard.

## Members

| Module | Does | Org switch |
| --- | --- | --- |
| [accounts](accounts/README.md) | Canvas, Google and Outlook sign-in for a member | |
| [games](games/README.md) | Jeopardy in Discord | |
| [points](points/README.md) | Points, leaderboards and CSV imports | `points` |
| [storefront](storefront/README.md) | Merch store paid in points | `storefront` |
| [users](users/README.md) | Members and memberships | |

## Automations

| Module | Does | Org switch |
| --- | --- | --- |
| [alerts](alerts/README.md) | Job and hackathon listings posted to Discord webhooks | `alerts` |
| [calendar](calendar/README.md) | Notion events synced to Google Calendar | `calendar` |
| [leetcode](leetcode/README.md) | The daily LeetCode post and solve checks | `leetcode` |

## Knowledge and agents

| Module | Does | Org switch |
| --- | --- | --- |
| [agents](agents/README.md) | Conversations, memories, profile graph and pending actions for agents | |
| [integrations](integrations/README.md) | Tools of connected services (GitHub) passed through to their MCP servers | |
| [knowledge](knowledge/README.md) | Sources, crawls and hybrid search | |
| [mcp](mcp/README.md) | The MCP server and `/api/tools` | |
| [packs](packs/README.md) | Loads the packs in `packs/`: campus pages and live queries added to knowledge | |

## Infrastructure

| Module | Does | Org switch |
| --- | --- | --- |
| [compute](compute/README.md) | Pods on a hosting provider (RunPod) that members connect to over SSH | `compute` |
| [runpod](runpod/README.md) | App deploys to a hosting provider (RunPod) | |

## Platform

| Module | Does | Org switch |
| --- | --- | --- |
| [auth](auth/README.md) | Discord sign-in, tokens, access checks, machine tokens and scopes | |
| [bot](bot/README.md) | The Discord bot and its helper cog | |
| [dashboard](dashboard/README.md) | Overview, branding and CI runs for the officer dashboard | |
| [organizations](organizations/README.md) | Orgs, config, module switches, secrets and machine tokens | |
| [public](public/README.md) | Open reads | |
| [superadmin](superadmin/README.md) | Orgs for the whole deployment | |

## Shared files

`registry.py` mounts each blueprint. `manifest.py` lists the categories and the model, job and tool modules. `cli.py` has the `flask --app main org`, `jobs` and `config` commands. `tests/test_module_layout.py` checks that each module is in these lists and in the docs.

The modules from SoDA (points, storefront, users, superadmin, calendar, organizations, public, auth, games) do not follow the module pattern in full. Each README lists its Known gaps.
