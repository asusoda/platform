# calendar

Syncs an org's Notion events database to its Google Calendar, and serves the org's upcoming events. Each org can use its own Notion token and Google service account as org secrets.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Open events, officer sync and setup, sync of all orgs, and legacy routes that return errors |
| `service.py` | `MultiOrgCalendarService`, `list_events`, `sync_organization`, `setup_calendar`, `sync_all`; declares `calendar:read` and the `notion_api_key` and `google_service_account` secrets |
| `clients/` | `GoogleCalendarClient` (`google.py`) and `NotionCalendarClient` (`notion.py`) |
| `sync.py` | Makes a Google Calendar match the Notion events |
| `events.py`, `dates.py` | `CalendarEventDTO` and Notion property reads; `DateParser` |
| `errors.py`, `tracing.py` | `APIErrorHandler` for Google and Notion errors; Sentry spans |
| `models.py`, `tools.py`, `jobs.py` | The event link table; the `events.list` tool; the sync job |

## Surface

- Routes: `/api/calendar`, behind the `calendar` switch. `/<org_prefix>/events` is open. `/<org_prefix>/sync` and `/setup` need an officer of the org. `/sync-all` needs a platform token. `/debug/organizations` needs an officer of any org.
- Jobs: `calendar.sync_all`, on the `CALENDAR_SYNC_CRON` schedule. No schedule if it is not set.
- Tools: `events.list` (scope `calendar:read`).
- Tables: `calendar_event_links` (not used by the sync).

See [docs/modules/calendar.md](../../docs/modules/calendar.md).
