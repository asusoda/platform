# Roadmap

This page lists what is left to build and the known faults. The other pages describe what Platform does now.

## Before wider use

- [ ] Turn on access enforcement (`ACCESS_ENFORCE=true`) on each deployment when its `access decision=would_deny` lines show no real callers.
- [ ] Move the SQLite deployments to Postgres with the copy script. Keep the SQLite file for one week of clean operation.
- [ ] Make `Check` a required status check on `main`.
- [ ] Check the RunPod request and response field names against the live RunPod API. The compute and runpod modules are tested against a fake only.
- [ ] Tie Jeopardy to an org. It is global because the bot process has no command channel from the API.

## Core

- [ ] Terms and role assignments for each term. Officer access stops when the term stops.
- [ ] Handover: a list of the org's outside accounts and the role that owns each. Show an alert when that role is empty.
- [ ] Visibility levels on shared tables (public, member, officer, restricted), applied in queries.
- [ ] Sync run history: a table of runs for each source with cursors, so that a sync can continue and a failure is visible.
- [ ] Webhooks that start jobs, at `/api/webhooks/<module>/<name>`.
- [ ] Dashboard pages for job history and retry.
- [ ] A member page for compute, so that members can see their pods and sessions without the CLI.
- [ ] Shared tracing for agents on Platform (OpenTelemetry, with a self-hosted viewer).
- [ ] Replace Create React App in `web/`, which is deprecated, with Vite.

## Modules

| Module | Does |
| --- | --- |
| `events` | Native events, registration, QR check-in and attendance. Check-ins give points |
| `members` | Roster and memberships for each term, on the `users` tables |
| `announcements` | One message to Discord, Slack and email after an officer approves it |
| `github` | An org's repos and issues, and app manifests from them |
| `notion`, `google_drive` | Pages and documents as knowledge sources |
| `forms`, `csv`, `sheets` | Imports. The points CSV upload becomes one use of `csv` |
| `analytics` | Discord activity counts with hashed ids and an opt-out command. It never keeps message text |
| `slack` | Slack as a second chat platform |
| `sponsors`, `hackathon` | Sponsor records and hackathon logistics |

Campus source modules such as `asu` are examples. Another campus adds its own pages and live queries the same way.

## Cleanup

- [x] Rename `modules/auth/decoraters.py` to `decorators.py`.
- [x] Move the `users` and membership tables and their helpers to `modules/users`, and the storefront queries to `modules/storefront/service.py`.
- [ ] Move the rest of the logic in `points/api.py` and `storefront/api.py` into their `service.py`.
- [ ] Remove dead routes: the camelCase aliases in points, `/api/users/<org>/submit-form`, `/api/public/getnextevent`, `/api/organizations/<id>/roles`, and the legacy calendar routes (`/events`, `/delete-all-events`, `/notion-webhook`).
- [ ] Remove the unused models `Session`, `OrganizationConfig` and `Officer`, and the unused columns `points_per_message` and `points_cooldown`.
- [ ] Make `superadmin` create orgs through `organizations.service.create_organization`, so that the prefix is checked.

## Known faults

- `DELETE /api/superadmin/remove_org/<id>` deletes the org row with no cascade. Rows that refer to the org stay, or the delete fails.
- Checkout reads the points balance and writes the purchase with no row lock. Two checkouts at the same time can both pass the balance check.
- `error_handler` returns the exception text to the client.
- `GET /api/organizations/<id>/stats`, `/activity` and `/roles` return fixed sample data.
- `superadmin_required` accepts a session only with `role == "admin"`, which sign-in never sets. Only the header path works.
- `GameCog` and `HelperCog` use `bot.guilds[0]`, the first server of the bot, not the org of the request. Game state is in memory and a restart loses it.
- The calendar sync needs the Notion properties `Name`, `Date`, `Location`, `Description` and `gcal_id`. If one has a different name, the sync skips the event and logs a warning.
- The points CSV upload gives no progress or result. Errors go only to the log.
- The CORS list in `main.py` does not have `localhost:5000`, the dev port of `web/`. Add it with `CORS_EXTRA_ORIGINS`.

## Not planned

- An agent that runs inside Platform. Agents are separate apps that call Platform with scoped tokens.
- Answer generation. Platform keeps and searches data; agents generate answers.
- Container orchestration for more than one pod for each app.
- Storage of Discord channel messages.

## Open questions

- [ ] Maintainers and CODEOWNERS for each module when more than one org contributes.
- [ ] Privacy defaults for agent data on each deployment: who can read conversations, and whether the 180-day retention must be shorter.
- [ ] Keep Flask, or move to FastAPI one blueprint at a time.
