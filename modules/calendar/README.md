# calendar

Syncs an organization's Notion events database to its Google Calendar and serves the org's upcoming events. Each org brings its own Notion token and Google service account as org secrets.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Public events, officer sync and setup, sync of every org, and legacy endpoints that answer with errors |
| `service.py` | `MultiOrgCalendarService` and `list_events`, `sync_organization`, `setup_calendar`, `sync_all`; declares the `calendar:read` scope and the `notion_api_key` and `google_service_account` secrets |
| `clients/` | `GoogleCalendarClient` (`google.py`) and `NotionCalendarClient` (`notion.py`) |
| `sync.py` | Makes a Google Calendar match the Notion events: create, update, delete duplicates and orphans |
| `events.py` | `CalendarEventDTO` and Notion property extraction |
| `dates.py` | `DateParser`: Notion dates in Google Calendar format |
| `tracing.py` | `operation_span`: Sentry spans |
| `models.py` | The table linking Notion pages to Google events |
| `errors.py` | `APIErrorHandler`: logs Google and Notion API errors and reports them to Sentry |
| `tools.py` | The `events.list` tool |
| `jobs.py` | The sync job |

## Surface

- Routes: `/api/calendar`, gated by the `calendar` switch. `/<org_prefix>/events` is public; `/<org_prefix>/sync` and `/<org_prefix>/setup` need an officer of that org; `/sync-all` needs a signed-in platform token; `/debug/organizations` needs an officer of any org.
- Jobs: `calendar.sync_all`, cron from `CALENDAR_SYNC_CRON`, not scheduled when unset.
- Tools: `events.list` (scope `calendar:read`, gated by `calendar`).
- Tables: `calendar_event_links`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
