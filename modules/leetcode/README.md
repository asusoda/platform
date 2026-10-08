# leetcode

Posts the LeetCode daily question in an organization's Discord channel, records which linked members solved it, and offers LeetCode slash commands.

## Files

| File | Holds |
| --- | --- |
| `cog.py` | `LeetCodeCog`: `/daily`, `/random`, `/link`, `/unlink`, `/leaderboard`, `/stats` |
| `daily.py` | The daily post and solve checks, run as jobs over Discord's REST API; one `leetcode_daily` row per date and target stops a double post |
| `service.py` | Links, solves, stats, and the org's LeetCode settings |
| `client.py` | LeetCode GraphQL client |
| `models.py` | Links, solves, daily posts |
| `jobs.py` | The post and verify jobs |

## Surface

- Routes: none of its own. Officers read and change the settings at `/api/organizations/<org_id>/leetcode`. The daily post is gated by the `leetcode` switch.
- Jobs: `leetcode.post_daily`, cron `*/5 * * * *`; `leetcode.verify`, cron `*/10 * * * *`.
- Tools: none.
- Tables: `leetcode_link`, `leetcode_solve`, `leetcode_daily`.

## Depends on

`core.discord_messages`, `core.discord_directory`, `core.jobs`, `core.logging_config`, `core.base`; `modules.organizations`; `shared`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
