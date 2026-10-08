# Roadmap

Platform is shared infrastructure for student organizations. One deployment serves many
organizations; each one is a Discord server and switches its optional modules on or off. This page
lists what is left to build. What already exists is described in the other pages in `docs/`.

## Before wider use

- [ ] Turn on access enforcement (`ACCESS_ENFORCE=true`) on each deployment after its
  `access decision=would_deny` log lines show no legitimate callers being refused.
- [ ] Move existing SQLite deployments to Postgres with the copy-and-verify script, and keep the
  SQLite file until a week of clean running.
- [ ] Make `Check` a required status check on `main`.
- [ ] Check the RunPod request and response field names against the live RunPod API. The compute
  and runpod modules are tested against a fake only.
- [ ] Tie Jeopardy to an organization. It is global today because the bot process has no command
  channel from the API.

## Core

- [ ] Terms and role assignments per term, with officer access ending when the term does.
- [ ] Handover: a registry of the club's external accounts and the role that owns each, flagged
  when that role is empty.
- [ ] Visibility levels on shared tables (public, member, officer, restricted), enforced in queries.
- [ ] Sync run history: a table of runs per source with cursors, so syncs resume and failures are
  visible.
- [ ] Webhooks turned into jobs at `/api/webhooks/<module>/<name>`.
- [ ] Web pages for jobs (history, retry) and for machine tokens.
- [ ] A member page for compute, so members can see their pods and sessions without the CLI.
- [ ] Shared tracing for agents built on the platform (OpenTelemetry, with a self-hosted viewer).
- [ ] Replace the Create React App frontend, which is deprecated, with Vite.

## Modules

| Module | What it does |
| --- | --- |
| `events` | Native events, registration, QR check-in and attendance. Points awards come from check-ins. |
| `members` | Roster and memberships per term, built on the existing users and memberships. |
| `announcements` | One message sent to Discord, Slack and email after an officer approves it. |
| `github` | An org's repositories and issues, and app manifests read from them. |
| `notion`, `google_drive` | Pages and documents as knowledge sources. |
| `forms`, `csv`, `sheets` | Imports. The points CSV upload becomes one use of `csv`. |
| `analytics` | Discord activity counts with hashed ids and an opt-out command. Message content is never stored. |
| `slack` | Slack as a second chat platform next to Discord. |
| `sponsors`, `hackathon` | Sponsor records and hackathon logistics. |

Campus source modules like `asu` are examples. Another campus adds its own pages and live queries
the same way.

## Cleanup

Found while documenting the modules. Each is small and local.

- [ ] Rename `modules/auth/decoraters.py` to `decorators.py`.
- [ ] Move the shared `users` and memberships tables and their helpers out of `modules/points` into
  `modules/users`, and the storefront queries out of `core/db.py` into `modules/storefront`.
- [ ] Move the logic in `points/api.py` and `storefront/api.py` into a `service.py` each.
- [ ] Remove dead routes and code: duplicate camelCase aliases in points, `/submit-form` in users,
  `/getnextevent` in public, fake `/roles` in organizations, three legacy calendar endpoints,
  unused models (`Session`, `OrganizationConfig`, `Officer`), `games/jeopardy/QuestionPost.py`.
- [ ] Remove hardcoded guild ids in `HelperCog` and the bot's own officer and member lookups, which
  repeat `core/discord_directory.py`.
- [ ] `superadmin` creates organizations through `organizations.service` so prefixes are validated,
  and stops logging the Authorization header.
- [ ] Share one HTML-to-text function between `asu/text.py` and `knowledge/extract.py`.

## Not planned

- An autonomous agent inside the platform. Agents are separate apps that call it with scoped tokens.
- Answer generation in the platform. It stores and searches; agents generate.
- Container orchestration beyond one pod per app.
- Storing Discord channel messages.

## Open questions

- [ ] Maintainers and CODEOWNERS per module once more than one club contributes.
- [ ] Privacy defaults for agent data per deployment: who can read conversations, and whether the
  180-day retention should be shorter.
- [ ] Whether to keep Flask or move to FastAPI one blueprint at a time.
