# Modules

One folder per feature. Each folder has a `README.md` with its files, routes, jobs, tools and
tables. [docs/writing-a-module.md](../docs/writing-a-module.md) describes the files a module has
and where a new one is registered.

| Module | What it does | Org switch |
| --- | --- | --- |
| [accounts](accounts/README.md) | Canvas, Google and Outlook sign-in for a member, bound to their Discord account | |
| [alerts](alerts/README.md) | Job and hackathon listings posted to Discord webhooks | `alerts` |
| [dashboard](dashboard/README.md) | Overview and CI runs for the officer dashboard | |
| [agents](agents/README.md) | Conversations, memories, profile graph and pending actions for agents | |
| [asu](asu/README.md) | Example campus source: public ASU pages and live queries, indexed into knowledge | |
| [auth](auth/README.md) | Discord login, JWTs, access checks, machine tokens and scopes | |
| [bot](bot/README.md) | The Discord bot process and its cogs | |
| [calendar](calendar/README.md) | Notion events synced to Google Calendar | `calendar` |
| [compute](compute/README.md) | RunPod pods members SSH into, file manager, scheduled sessions | `compute` |
| [games](games/README.md) | Jeopardy in Discord | |
| [knowledge](knowledge/README.md) | Sources, crawls and hybrid search | |
| [leetcode](leetcode/README.md) | Daily LeetCode post and solve checks | `leetcode` |
| [mcp](mcp/README.md) | MCP server and `/api/tools` over every module's tools | |
| [organizations](organizations/README.md) | Orgs, officers, config and module switches | |
| [points](points/README.md) | Members, points, leaderboards, CSV imports | `points` |
| [public](public/README.md) | Unauthenticated reads | |
| [runpod](runpod/README.md) | App deploys to RunPod with health checks and rollback | |
| [storefront](storefront/README.md) | Merch store paid in points | `storefront` |
| [superadmin](superadmin/README.md) | Installing and managing organizations across the deployment | |
| [users](users/README.md) | Member records within an org | |

`registry.py` mounts every blueprint and lists the job and tool modules. `cli.py` holds the
`flask --app main org` commands.
