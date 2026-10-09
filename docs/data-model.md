# Data model

This page lists each table, the module that owns it, and the rules to change the schema. The models are SQLAlchemy classes that use `Base` from `core/db/base.py`. `modules/manifest.py` lists every model module.

## The core tables

- `organizations`: one row for each org, which is one Discord server. `prefix` is the URL name and `guild_id` is the server id. `officer_role_id` is the Discord role that makes a member an officer. If it is empty, the org has no officers. `config` is a JSON object with the module switches, branding and module settings.
- `users`: one row for each person, for all orgs. `discord_id`, `username`, `email`, `student_id` and `uuid` are each unique and can be empty. A lookup can thus try more than one of them.
- `user_organization_memberships`: the link between a member and an org, with `is_active` and the org's own `profile_fields`. A member must have an active membership to get points or to buy in the store.
- `points`: a ledger with one row for each change. The balance is `SUM(points)` for a member and an org. A purchase adds a negative row.

Rows that belong to an org have an `organization_id` column. Discord roles decide who is an officer, not a table. A role change in Discord thus changes access at the next request (the cache keeps the result for 60 seconds).

## All tables

| Module | Tables |
| --- | --- |
| core | `audit_log` (successful changes and job runs), `error_groups` (errors of each process and the dashboard, grouped), `org_secrets` (org secrets, encrypted with `SECRETS_KEY`) |
| organizations | `organizations`, `organization_configs` and `officers` (not used) |
| users | `users`, `user_organization_memberships` |
| points | `points` |
| storefront | `products` (price in points), `orders`, `order_items` (keeps the price at the time of the order) |
| auth | `refresh_tokens` (hash only), `revoked_tokens`, `app_tokens`, `machine_tokens` (hash only, scopes, and per-integration `limits`), `sessions` (not used) |
| calendar | `calendar_event_links` (not used by the sync, which uses Google event properties) |
| games | `jeopardy_game`, `active_game` (one active game for the deployment) |
| leetcode | `leetcode_link`, `leetcode_solve` (one solve for each member and day), `leetcode_daily` |
| accounts | `account_grants`, `account_logins` |
| agents | `agent_conversations`, `agent_messages`, `agent_memories`, `agent_profile_nodes`, `agent_profile_edges`, `agent_pending_actions` |
| knowledge | `knowledge_sources`, `knowledge_versions`, `knowledge_chunks`, `knowledge_runs` (one row for each crawl or upload) |
| compute | `compute_pods`, `compute_keys`, `compute_sessions` |
| runpod | `runpod_apps`, `runpod_deployments` |
| alerts | `alert_feeds`, `alert_posts`, `alert_runs` (one row for each feed run) |
| jobs | `procrastinate_*` (Postgres only, from the Procrastinate SQL, not from models) |

`audit_log` has one row for each successful POST, PUT, PATCH or DELETE under `/api`, and one row for each job run. It keeps the route, org, caller, status and path. It never keeps request bodies or file contents. The `audit.prune` job removes rows older than `AUDIT_RETENTION_DAYS` (default 365).

`error_groups` has one row for each distinct error. Errors with the same source, org, exception type and first frame in this repo add to one row: `count` goes up and `last_seen`, `message` and `stack` change. A resolved row opens again when its error happens again. The `error_log.prune` job removes rows not seen for `ERROR_RETENTION_DAYS` (default 90).

## Migrations

Alembic owns the schema on SQLite and Postgres. Nothing creates tables when the app starts. The API container runs `alembic upgrade head` before gunicorn. The tests make their schema with `create_all`.

```bash
uv run alembic upgrade head                            # apply migrations (make migrate)
uv run alembic revision --autogenerate -m "Add x"      # make a migration after a model change
uv run alembic check                                   # fail if the models and migrations do not agree
uv run alembic downgrade -1                            # go back one migration
```

- `make ci` runs `alembic upgrade head` and `alembic check` on a new database. If you change a model and do not add a migration, CI fails.
- `alembic/env.py` uses `render_as_batch=True`, because SQLite cannot alter a column. Alembic copies the table to make the change.
- `DATABASE_URL` overrides the URL in `alembic.ini`.
- `alembic/env.py` ignores the `procrastinate_*` tables and the indexes that migrations make with raw SQL (pgvector HNSW and full text GIN).

The `migration` skill in `.agents/skills/` has the full procedure.
