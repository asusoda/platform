# Integrations

An integration is an account or a service outside Platform, such as Notion or RunPod. An officer connects it one time on the dashboard's Integrations page. Then each module that needs it uses it. Each card shows whether the integration is connected, the modules that use it, a Test button and a link to its docs.

The page shows the cards in two groups:

- Accounts: the org's accounts at other services. Discord, GitHub, Google, Notion and RunPod.
- Services: servers that Platform calls for search and page reads. Embeddings, Firecrawl, OpenRouter and SearXNG.

The description of a card says what the officer connects, not what each module does with it. The "Used by" links show the modules.

## The integrations

| Integration | Keys (optional in brackets) | Default from .env | Used by |
| --- | --- | --- | --- |
| Discord | none for the org | `BOT_TOKEN` | Sign-in, LeetCode |
| Embeddings | `embeddings_url`, `embeddings_model`, [`embeddings_api_key`, `embeddings_query_prefix`] | `EMBEDDINGS_URL`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_API_KEY`, `EMBEDDINGS_QUERY_PREFIX` | Knowledge, MCP |
| Firecrawl | `firecrawl_url`, [`firecrawl_api_key`] | `FIRECRAWL_URL`, `FIRECRAWL_API_KEY` | Knowledge, ASU |
| GitHub | `github_token` | none | CI runs, Apps |
| Google | `google_service_account` (JSON key) | `google-secret.json` | Calendar sync |
| Notion | `notion_api_key` | `NOTION_API_KEY` | Calendar sync |
| OpenRouter | `openrouter_api_key` | `OPENROUTER_API_KEY` | Knowledge, MCP (through Embeddings) |
| RunPod | `runpod_api_key` | none | Compute, Apps |
| Web search (SearXNG) | `searxng_url`, [`searxng_engines`] | `SEARXNG_URL`, `SEARXNG_ENGINES` | ASU |

The keys are org secrets, encrypted with `SECRETS_KEY`. The API never returns a secret key. It returns the value of a field that is not secret, such as a URL or a model name, so the form can show it. When an org saves its own keys, they replace the deployment default for that org as a whole: Platform never mixes an org URL with a deployment key. An org must set every required field. Discord is set only in `.env`, for every org.

A URL that an org saves must be http or https on a host with only public addresses. Platform checks this when the org saves the URL and again before each call, and does not follow redirects. A deployment default in `.env` can be on the private network, such as `http://firecrawl:3002`.

Search compares only vectors of the same embedding model. An org with its own model searches its own vectors, and the vectors of public sources only if the publisher used the same model. Text search still covers every source. On Postgres the vector column holds 1024 numbers, so the model must return 1024. Test says so when it does not.

A card has one of three states:

- **Connected**: the org saved its own keys.
- **Deployment default**: the org has no keys, and `.env` gives a default.
- **Not connected**: neither.

Test connects with the key the module uses and shows the result. It does not change anything.

If Firecrawl is not connected, knowledge reads pages with a plain GET. If SearXNG is not connected, the ASU web live query returns 503.

## OpenRouter

OpenRouter gives one API key for many hosted models, with an OpenAI-compatible API at `https://openrouter.ai/api/v1`. Embeddings is the only part of Platform that calls a model. To use OpenRouter for embeddings:

1. On the OpenRouter card, set the API key. Or set `OPENROUTER_API_KEY` in `.env` for every org.
2. On the Embeddings card, set the base URL to `https://openrouter.ai/api/v1`.
3. Set the model to an OpenRouter embeddings model that returns 1024 numbers, such as `baai/bge-m3`.
4. Leave the Embeddings API key empty.
5. Click Test on the Embeddings card. It shows the number of dimensions.

If the Embeddings base URL is https on `openrouter.ai` and the Embeddings API key is empty, Platform sends the OpenRouter key. Org Embeddings settings use only the org's OpenRouter key, never `OPENROUTER_API_KEY`. The `.env` default works the same way: `EMBEDDINGS_URL` with no `EMBEDDINGS_API_KEY` uses `OPENROUTER_API_KEY`. An Embeddings API key, when set, always wins. Platform sends the OpenRouter key only to `https://openrouter.ai`.

Test on the OpenRouter card reads the key's name and credit limit from OpenRouter. It does not show the key.

## Routes

All routes are under `/api/dashboard/<org>`, for officers of the org.

| Route | Does |
| --- | --- |
| `GET /integrations` | Each integration, its fields, its state and the modules that use it |
| `PUT /integrations/<key>` | Body `{"fields": {"<secret name>": "<value>" or null}}`. null removes that key |
| `POST /integrations/<key>/test` | `{"ok": true or false, "message": "..."}` |

The older routes `/api/organizations/<id>/secrets/<name>` still work and write the same secrets.

## What stays in .env

A setting stays in `.env` when it is the same for every org or when it is about the server itself:

- Server and security: `DATABASE_URL`, `SECRET_KEY`, `SECRETS_KEY`, `ACCESS_ENFORCE`, `DISABLED_ROUTES`, `SENTRY_DSN`, `LOG_FORMAT`, `JOBS_BACKEND`, `MCP_PORT`.
- The one Discord app and the sign-in: `BOT_TOKEN`, `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`, `SYS_ADMIN`, the Clerk keys.
- The OAuth apps of connected accounts (`ACCOUNTS_*`). Their callback URLs are on the API, so one app serves every org.
- URLs of the frontends and CORS: `CLIENT_URL`, `DASHBOARD_URL`, `CORS_EXTRA_ORIGINS`.
- Limits and schedules of jobs: `CALENDAR_SYNC_CRON`, `AUDIT_RETENTION_DAYS`, `ERROR_RETENTION_DAYS`, `ERROR_WEBHOOK_URL`, `AGENT_RETENTION_DAYS`, `KNOWLEDGE_CRAWL_*`, `ASU_QUERY_MAX_CHARS`.
- `COMPUTE_CLI_NAME`: the name of the one CLI that talks to this API.

These settings moved to the dashboard, and the `.env` value is now the default for orgs that set none:

| `.env` | Dashboard |
| --- | --- |
| `EMBEDDINGS_*`, `FIRECRAWL_*`, `SEARXNG_*`, `NOTION_API_KEY`, `OPENROUTER_API_KEY` | Integrations |
| `COMPUTE_POD_IMAGE` | Compute > Settings |
| `KNOWLEDGE_PUBLISHERS` | Superadmin > Knowledge publishers. Orgs in `.env` stay publishers |
| `KNOWLEDGE_CHUNK_CHARS`, `KNOWLEDGE_MAX_DISTANCE` | Knowledge > Search settings |
| `LEETCODE_*` | LeetCode. The `.env` post is the older post for one server |

## Add an integration

1. Write a test function `(db, org_id) -> str` that connects and returns a short result. It raises `IntegrationError` with the reason when it fails. It never puts a key in the message.
2. Call `register(Integration(...))` from `core/integrations/registry.py` in the file that owns the client: a file in `core/integrations/` for a service that core uses, or a module file. Give the key, title, description, fields, docs page and test. The description says what the officer connects, such as "Connect the org's Notion workspace." `register` declares each field as an org secret. Give a field `secret=False` when the dashboard may show its value, `optional=True` when the org may leave it empty, and `kind="url"` for a URL that must be public.
3. Read the org's values with `org_values(db, org_id, key)`. It returns None when the org did not set every required field; then use the `.env` default.
4. In each module that reads the service, call `use("<key>", "<module>")` at the top of the file.
5. Add the module name to `MODULES` in `dashboard/src/pages/integrations.tsx` if it has a dashboard page, and an icon to `ICONS`. If it is an account, add its key to the Accounts group in `GROUPS`. A key in no group shows under Services.
6. Add a row to the table on this page.
