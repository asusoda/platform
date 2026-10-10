# games

Runs Jeopardy games in an organization's Discord server. Officers upload games, pick the active one and drive it from the web app; `GameCog` creates the team roles and channels, posts questions and keeps the scoreboard.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Game controls: upload, list, set and start the active game, reveal questions and answers, award team points, bot status |
| `cog.py` | `GameCog`: sets up and removes the game's channels and roles, sign-up, questions, scoreboard |
| `ui.py` | Discord views for question posts and answered questions |
| `jeopardy/` | The game, question and team classes |
| `models.py` | Stored games and the active game |

## Surface

- Routes: `/api/bot`, no module switch. Every route needs an officer of any org. Routes that drive a game need the bot running in the API process (`current_app.auth_bot`).
- Jobs: none.
- Tools: none.
- Tables: `jeopardy_game`, `active_game`.

## Depends on

`core.logging_config`, `core.base`; `modules.auth.access`; `HelperCog` from `modules/bot` through `bot.execute`; `shared`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
