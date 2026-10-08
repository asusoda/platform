# bot

The Discord gateway bot. `factory.create_bot` builds the bot from `bot.py` and adds `HelperCog`, `GameCog` from games and `LeetCodeCog` from leetcode. `bot_main.py` runs it as its own process; `main.py` runs it in a thread when `RUN_BOT_IN_API` is true.

## Files

| File | Holds |
| --- | --- |
| `factory.py` | `create_bot(loop)`: the bot with its cogs |
| `bot.py` | `BotFork`, a py-cord `Bot` subclass: the active game, and `execute(cog, method)` to call another cog's method |
| `cogs/helper.py` | `HelperCog`: creates and deletes categories, channels and roles for other cogs, sends and edits messages, tracks reactions for game sign-up, and the `/clear` slash command that removes the Jeopardy channels and team roles |

## Surface

- Routes: none. The game controls mounted at `/api/bot` live in `modules/games`.
- Jobs: none.
- Tools: none.
- Tables: none.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
