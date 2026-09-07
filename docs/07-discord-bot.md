# 7. The Discord Bot

## How it starts

One bot instance, running in one daemon thread with its own asyncio event loop.

`main.py:run_auth_bot_in_thread()`:

```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
auth_bot_instance = create_auth_bot(loop)   # from shared.py
app.auth_bot = auth_bot_instance            # ← how Flask handlers reach the bot
loop.run_until_complete(auth_bot_instance.start(config.BOT_TOKEN))
```

`shared.py:create_auth_bot(loop)` builds a `BotFork` with `Intents.default()` plus `members` and
`guilds`, then registers three cogs:

- `HelperCog`
- `GameCog`
- `LeetCodeCog(bot, db_connect, channel_id, role_ping, daily_time, timezone)` — the LeetCode config
  values are parsed from the env here, with warnings (not crashes) on bad values.

> **The `members` intent is privileged.** It must be enabled in the Discord Developer Portal for
> your application, or `guild.get_member()` returns `None` for everyone and every officer/membership
> check silently fails.

## `BotFork` — `modules/bot/discord_modules/bot.py`

Extends `discord.ext.commands.Bot` (py-cord). It adds the synchronous helpers Flask needs, since
Flask handlers cannot await inside the bot's loop.

| Method | Used by | What it does |
|--------|---------|--------------|
| `check_officer(user_id, superadmin_user_id)` | `/api/auth/callback`, `@superadmin_required` | Returns a list of guild ids where the user holds that org's `officer_role_id`. **Short-circuits: if `user_id == superadmin_user_id`, returns every guild the bot is in.** Skips orgs with no `officer_role_id` set. |
| `check_user_membership(user_id, guild_id)` | `@member_required` | Is this user in this guild? |
| `check_role` / `check_user_officer_status` | ad hoc | Does a member hold a role? |
| `get_guild_roles(guild_id)` | superadmin API | All roles in a guild |
| `get_name(user_id)` | `/api/auth/callback` | Display name (nick, else username). **Hardcoded to guild `762811961238618122`** — SoDA's own server. Users who are officers elsewhere but not in that guild get `None`. |
| `get_guilds()` | superadmin dashboard | All guilds |
| `execute(cog_name, command, *args, priority=...)` | `/api/bot/*` routes | Calls a method on a cog from outside the loop. `priority="NORMAL"` schedules a task on the loop; `priority="NOW"` applies `nest_asyncio` and runs it immediately. |

All of these read py-cord's **in-memory cache**, so they are cheap but only correct once the bot has
connected and populated its guilds. That is why so many handlers guard with
`if not auth_bot.is_ready(): return 503`.

`execute()` is the bridge between the HTTP world and the Discord world, and it is the reason the
Jeopardy HTTP endpoints work at all.

---

## `LeetCodeCog` — the daily challenge

`modules/bot/discord_modules/cogs/LeetCodeCog.py`, with GraphQL calls in
`modules/bot/discord_modules/utils/leetcode.py`.

### Slash commands

| Command | Ephemeral? | Description |
|---------|-----------|-------------|
| `/daily` | no | Today's LeetCode daily challenge as an embed |
| `/random [difficulty]` | no | A random problem, optionally filtered Easy/Medium/Hard |
| `/link <username>` | yes | Link your Discord account to a LeetCode handle. Validated by fetching one recent submission — an unknown handle is rejected with a clear message. |
| `/unlink` | yes | Remove your link |
| `/leaderboard [limit]` | no | Top daily solvers, 1–25 entries, medals for the top three |
| `/stats` | no | `{linked users, active solvers, total solves}` server-wide |

### The daily post and verification loop

```
on_ready
  └─ _start_daily_task()
       parse LEETCODE_DAILY_TIME as HH:MM (falls back to 09:00 on a bad value)
       schedule post_daily at that time in TIMEZONE

post_daily (tasks.loop hours=24, pinned to a time)
  ├─ resolve LEETCODE_CHANNEL_ID (get_channel, then fetch_channel)
  ├─ fetch today's daily question from LeetCode's GraphQL API
  ├─ send the embed, optionally pinging LEETCODE_ROLE_PING, and add a ✅ reaction
  └─ reset state:
       _today_slug, _today_date, _daily_message
       _verified_today = {}
       _pending_today  = every discord_id in leetcode_link
     then start (or restart) verify_loop, unless nobody is linked

verify_loop (tasks.loop minutes=10)
  ├─ stop if there is no live challenge
  ├─ stop if the date in TIMEZONE has rolled over
  ├─ stop if _pending_today is empty
  └─ for each pending user:
       fetch their last 20 accepted submissions
       any submission whose titleSlug == today's slug, dated today in TIMEZONE?
         → move them pending → verified
         → insert a leetcode_solve row
         → reply to the daily message: "✅ @user solved today's challenge as **handle**!"
```

`/link` during a live challenge opts the new user into the current poll immediately.

### Things worth knowing

- LeetCode's API is unauthenticated and unofficial. `fetch_random_question` makes **two** calls: one
  to learn the total count, one to fetch at a random offset (`secrets.randbelow`). Every call has a
  10-second timeout and raises `RuntimeError` on non-200 or GraphQL errors.
- Verification polls every 10 minutes, so a solve is acknowledged within ~10 minutes, not instantly.
- `leetcode_solve` has a unique constraint on `(discord_id, solved_date)`. The leaderboard therefore
  counts **days participated**, not problems solved.
- LeetCode data is **global**, not org-scoped. One channel, one leaderboard, across all guilds.
- If `LEETCODE_CHANNEL_ID` is unset, `post_daily` never starts and no verification happens — but the
  slash commands still work.

---

## `HelperCog` — guild plumbing

A thin async wrapper over Discord operations that GameCog needs:

- Create/delete: categories, text channels, voice channels, roles
- Send / edit messages, add reactions
- `add_to_listner(message, emoji)` / `remove_from_listner(...)` — register a message+emoji pair
- `on_reaction_add` / `on_reaction_remove` listeners — when someone reacts to a registered message
  with the registered emoji, they are added to (or removed from) the game roster
- One slash command: `/clear`

The reaction listener is the enrolment mechanism for Jeopardy: the announcement embed gets a ✅
reaction, and reacting adds you as a player.

(The misspelling "listner" is in the source. Consistent, so leave it.)

---

## Jeopardy

Three layers:

### 1. Game model — `discord_modules/cogs/jeopardy/`

Pure Python, no Discord dependency beyond type hints:

- **`JeopardyGame`** — built from a game JSON: `name`, `description`, `teams`, `categories`,
  `per_category`, `questions`. Tracks `is_announced`, `is_started`, and a `uuid`. Handles
  `get_question`, `mark_question_as_answered`, `award_points`, `get_winners`, `get_board`.
- **`JeopardyQuestion`** — category, question, answer, value.
- **`Team`** — name, score, member ids, and the Discord role attached to it.
- **`QuestionPost`** — a button view for a posted question.

### 2. Discord orchestration — `GameCog`

Holds all live game state as **instance attributes on the cog** (`game`, `game_category`, `roles`,
`announcement_channel`, `voice_channels`, `scoreboard_channel`, `gameboard`, `question_post`,
`stage`, `guild`).

`setup_game()`:
1. Picks `self.bot.guilds[0]` — **the first guild the bot joined**, not the org you are acting on.
2. Creates a `Jeopardy` category, moves it to position 0.
3. Creates a stage channel.
4. Per team: creates a role and a voice channel that only that role may connect to.
5. Creates an `announcements` text channel, posts the announcement embed, adds ✅, and registers
   that message with `HelperCog.add_to_listner`.

`start_game()` then creates the scoreboard channel, attaches roles to teams, shuffles players into
teams (`balance_teams`), assigns Discord roles, and renders the scoreboard and gameboard.

Then `show_question` / `show_answer` / `award_points` / `update_scoreboard` / `update_gameboard` /
`end_game` drive the game.

### 3. HTTP control — `modules/bot/api.py`

The React `GamePanel` / `ActiveGame` pages drive the game over HTTP. Each route validates input,
reads or writes the `jeopardy_game` / `active_game` tables, and calls
`bot.execute("GameCog", "<method>", ...)` to reach the cog.

### Jeopardy limitations to be aware of

- **One game at a time, globally.** `active_game` is queried with `.first()`; game state lives on a
  single cog instance.
- **Not org-aware.** `setup_game` uses `self.bot.guilds[0]`.
- **State is in memory.** Restart the API and a game in progress loses its channel/role references,
  leaving orphaned Discord channels and roles that must be cleaned up by hand.
- **The endpoints are unauthenticated.** See [Gotchas](./10-gotchas-and-known-issues.md).
