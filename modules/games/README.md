# games

Runs Jeopardy games in an org's Discord server. Officers upload games, select the active one and run it from the web app. `GameCog` makes the team roles and channels, posts questions and keeps the scoreboard.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Game controls: upload, list, set and start the active game, show questions and answers, give team points |
| `service.py` | The game JSON check, and reads of a game file from `./data` |
| `cog.py` | `GameCog`: game channels and roles, sign-up, questions, scoreboard |
| `ui.py` | Discord views for question posts |
| `jeopardy/` | `JeopardyGame`, `JeopardyQuestion`, `Team` |
| `models.py` | Stored games and the active game |

## Surface

- Routes: `/api/bot`. Each route needs an officer of any org. The routes that run a game need the bot in the API process (`current_app.auth_bot`), so they fail under gunicorn.
- Jobs: none.
- Tools: none.
- Tables: `jeopardy_game`, `active_game`. One game runs at a time for the deployment, in the first server of the bot.
