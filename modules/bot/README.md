# bot

The Discord gateway bot. `shared.create_auth_bot` builds the bot from `discord_modules/bot.py` and adds `HelperCog`, `GameCog` from games and `LeetCodeCog` from leetcode. `bot_main.py` runs it as its own process; `main.py` runs it in a thread when `RUN_BOT_IN_API` is true.

## Files

| File | Holds |
| --- | --- |
| `discord_modules/bot.py` | The bot class, a py-cord `Bot` subclass: start and stop, `execute(cog, method)` to call another cog's method, guild, role and officer lookups |
| `discord_modules/cogs/HelperCog.py` | Creates and deletes categories, channels and roles for other cogs, sends and edits messages, tracks reactions for game sign-up, and the `/clear` slash command that removes the Jeopardy channels and team roles |

## Surface

- Routes: none. The game controls mounted at `/api/bot` live in `modules/games`.
- Jobs: none.
- Tools: none.
- Tables: none.

## Depends on

`core.logging_config`; `modules.organizations.models`; `shared`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
