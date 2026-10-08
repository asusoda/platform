# Modules

One folder for each module. Each folder has a `README.md` with its files and its surface: routes, jobs, tools and tables. [docs/writing-a-module.md](../docs/writing-a-module.md) gives the rules and the places to register a new module.

| Module | Does | Org switch |
| --- | --- | --- |
| [accounts](accounts/README.md) | Canvas, Google and Outlook sign-in for a member | |
| [agents](agents/README.md) | Conversations, memories, profile graph and pending actions for agents | |
| [alerts](alerts/README.md) | Job and hackathon listings posted to Discord webhooks | `alerts` |
| [asu](asu/README.md) | Example campus source: ASU pages and live queries | |
| [auth](auth/README.md) | Discord sign-in, tokens, access checks, machine tokens and scopes | |
| [bot](bot/README.md) | The Discord bot and its helper cog | |
| [calendar](calendar/README.md) | Notion events synced to Google Calendar | `calendar` |
| [compute](compute/README.md) | RunPod pods that members connect to over SSH | `compute` |
| [dashboard](dashboard/README.md) | Overview, branding and CI runs for the officer dashboard | |
| [games](games/README.md) | Jeopardy in Discord | |
| [knowledge](knowledge/README.md) | Sources, crawls and hybrid search | |
| [leetcode](leetcode/README.md) | The daily LeetCode post and solve checks | `leetcode` |
| [mcp](mcp/README.md) | The MCP server and `/api/tools` | |
| [organizations](organizations/README.md) | Orgs, config, module switches, secrets and machine tokens | |
| [points](points/README.md) | Points, leaderboards and CSV imports | `points` |
| [public](public/README.md) | Open reads | |
| [runpod](runpod/README.md) | App deploys to RunPod | |
| [storefront](storefront/README.md) | Merch store paid in points | `storefront` |
| [superadmin](superadmin/README.md) | Orgs for the whole deployment | |
| [users](users/README.md) | Members and memberships | |

`registry.py` mounts each blueprint. `manifest.py` lists the model, job and tool modules. `cli.py` has the `flask --app main org`, `jobs` and `config` commands.
