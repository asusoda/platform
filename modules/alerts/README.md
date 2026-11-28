# alerts

Sends the org's events, such as a failed job or a site that is down, to its destinations. A destination is a Discord webhook with a name and the events it gets: its routes. Feeds post to a destination too. Alerts is a Core module, so it is always on. Activity saves each event as a notification, also when no destination gets it.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes to list, add, change, delete and test destinations, and to read the deliveries log |
| `service.py` | Checks of the name, events and URL; the encrypted URL and its hint; the test message; a delete refused while a feed posts to the destination; the deliveries log |
| `delivery.py` | The one send path: `deliver()` posts a message and logs it, `log_post()` logs a bot post, `send_event()` sends an event to the org's destinations. The kinds (Discord) |
| `models.py` | `Destination` (table `webhooks`) and `Delivery` (table `deliveries`) |
| `jobs.py` | `alerts.prune`; importing it adds the `events.deliver` handler in the worker |
| `tools.py` | The `access.*webhook*` tools; declares `webhooks:manage` |

`core/webhooks.py` has the events that modules declare, `emit()` and the `events.deliver` job.

## Surface

- Routes: `/api/dashboard/<org>/webhooks`, `/webhooks/<id>`, `/webhooks/<id>/test` and `/webhooks/deliveries`. Officers of the org only.
- Jobs: `alerts.prune`, schedule `20 4 * * *`, deletes `deliveries` rows older than 30 days.
- Tools: `access.webhooks`, `access.save_webhook`, `access.test_webhook`, `access.delete_webhook` (confirm) (scope `webhooks:manage`). URLs are never returned. Tools marked confirm run only with `confirm=true`.
- Tables: `webhooks` (one row for each destination), `deliveries` (each message sent or tried).
- Limits: `alerts.destinations` (default 20), `alerts.messages` (30 an hour for each event). See [docs/limits.md](../../docs/limits.md).
- Migration `c6e8a0b2d4f6` made it from the `event_webhook` module. An org that had that switch off got its destinations turned off.

See [docs/webhooks.md](../../docs/webhooks.md).
