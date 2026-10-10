# leetcode

Posts the LeetCode daily question in an org's Discord channel, records which linked members solved it, and adds LeetCode slash commands.

## Files

| File | Holds |
| --- | --- |
| `cog.py` | `LeetCodeCog`: `/daily`, `/random`, `/link`, `/unlink`, `/leaderboard`, `/stats` |
| `daily.py` | The daily post and solve checks over Discord's REST API; one `leetcode_daily` row for each date and target stops a second post |
| `service.py` | Links, solves, stats and the org's LeetCode settings |
| `client.py` | The LeetCode GraphQL client |
| `models.py`, `jobs.py`, `tools.py` | Links, solves and daily posts; the post and verify jobs; the settings tools |

## Surface

- Routes: none of its own. Officers set `channel_id`, `role_ping` and `daily_time` with `GET` and `PUT /api/organizations/<org_id>/leetcode`. The `leetcode` switch turns off the org's post.
- Jobs: `leetcode.post_daily`, schedule `*/5 * * * *`; `leetcode.verify`, schedule `*/10 * * * *`.
- Tools: `leetcode.settings` (scope `org:read`); `leetcode.update_settings` (scope `settings:write`).
- Tables: `leetcode_link`, `leetcode_solve` (one solve for each member and day), `leetcode_daily`.

`LEETCODE_CHANNEL_ID`, `LEETCODE_ROLE_PING` and `LEETCODE_DAILY_TIME` set one more post for the deployment. To move it to an org, set the org's channel, then remove `LEETCODE_CHANNEL_ID`. If you do not, the channel gets two posts.
