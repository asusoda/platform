# bot

The Discord gateway bot. `bot_main.py` runs it as its own process. `main.py` runs it in a thread when `RUN_BOT_IN_API` is true.

## Files

| File | Holds |
| --- | --- |
| `factory.py` | `create_bot(loop)`: the bot with `HelperCog`, `GameCog` (from games) and `LeetCodeCog` (from leetcode) |
| `bot.py` | `BotFork`, a py-cord `Bot`: the active game, and `execute(cog, method)` to call a cog method from a route |
| `cogs/helper.py` | `HelperCog`: categories, channels, roles, messages and reactions for other cogs; game sign-up by reaction; `/clear` |

The `members` intent is privileged. Turn it on for the app in the Discord Developer Portal, or member lookups return nothing.

## Surface

- Routes: none. The game routes at `/api/bot` are in `modules/games`.
- Jobs: none. The LeetCode post runs as a job in `modules/leetcode`.
- Tools: none.
- Tables: none.
