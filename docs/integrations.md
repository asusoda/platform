# Integrations

An integration is an outside service that modules use, such as Notion or RunPod. Officers connect them on the dashboard's Integrations page. Each card shows whether the service is connected, the modules that use it, a Test button and a link to its docs.

## The integrations

| Integration | Keys | Default from .env | Used by |
| --- | --- | --- | --- |
| Discord | none for the org | `BOT_TOKEN` | Sign-in, LeetCode |
| Embeddings | none for the org | `EMBEDDINGS_URL`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_API_KEY` | Knowledge |
| GitHub | `github_token` | none | CI runs, Apps |
| Google | `google_service_account` (JSON key) | `google-secret.json` | Calendar |
| Notion | `notion_api_key` | `NOTION_API_KEY` | Calendar |
| RunPod | `runpod_api_key` | none | Compute, Apps |

The keys are org secrets, encrypted with `SECRETS_KEY`. The API never returns them. When an org saves its own key, it replaces the deployment default for that org. Discord and Embeddings are set only in `.env`, for every org.

A card has one of three states:

- **Connected**: the org saved its own keys.
- **Deployment default**: the org has no keys, and `.env` gives a default.
- **Not connected**: neither.

Test connects with the key the module uses and shows the result. It does not change anything.

## Routes

All routes are under `/api/dashboard/<org>`, for officers of the org.

| Route | Does |
| --- | --- |
| `GET /integrations` | Each integration, its fields, its state and the modules that use it |
| `PUT /integrations/<key>` | Body `{"fields": {"<secret name>": "<value>" or null}}`. null removes that key |
| `POST /integrations/<key>/test` | `{"ok": true or false, "message": "..."}` |

The older routes `/api/organizations/<id>/secrets/<name>` still work and write the same secrets.

## Add an integration

1. Write a test function `(db, org_id) -> str` that connects and returns a short result. It raises `IntegrationError` with the reason when it fails. It never puts a key in the message.
2. Call `register(Integration(...))` from `core/integrations/registry.py` in the file that owns the client: a file in `core/integrations/` for a service that core uses, or a module file. Give the key, title, description, fields, docs page and test. `register` declares each field as an org secret.
3. In each module that reads the service, call `use("<key>", "<module>")` at the top of the file.
4. Add the module name to `MODULES` in `dashboard/src/pages/integrations.tsx` if it has a dashboard page, and an icon to `ICONS`.
5. Add a row to the table on this page.
