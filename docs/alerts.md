# Alerts module

Posts new job listings and upcoming hackathons to Discord. An organization adds feeds; each feed
reads one source on a schedule and posts items it has not posted before to one Discord webhook.

## Feeds

| Kind | Source | Item key |
| --- | --- | --- |
| `github_jobs` | The job table in a GitHub repository's README (Company, Role, Location, Application/Link, Date Posted), as in the internship and new grad lists | Hash of company, role, first location and link without tracking parameters |
| `hackathons` | Hack Club, Euro-Hackathons and Hackalist | Event name, lowercased |

A feed's first run records every current item without posting it, so adding a feed does not post
hundreds of old listings. Later runs post new items, up to 25 per run, half a second apart. An
item that fails to post stays new and goes out on the next run.

## Routes

All under `/api/alerts/<org>`, for officers of the org. The `alerts` module switch gates them.

| Method and path | Does |
| --- | --- |
| `GET /feeds` | Every feed with its schedule, last run, last error and number of items posted |
| `GET /feeds/<key>` | One feed |
| `PUT /feeds/<key>` | Create (201) or update (200). Body below |
| `DELETE /feeds/<key>` | Delete the feed, its posted items and its webhook secret |
| `POST /feeds/<key>/run` | Queue a run now. `{"post_existing": true}` posts current items on a first run instead of recording them. 202 |

`PUT` body:

```json
{
  "kind": "github_jobs",
  "webhook_url": "https://discord.com/api/webhooks/<id>/<token>",
  "every_hours": 3,
  "enabled": true,
  "config": {"repo": "vanshb03/Summer2026-Internships", "label": "Internship"}
}
```

- The key is lowercase letters, digits and dashes, up to 40 characters.
- `webhook_url` is required when creating a feed and optional after. It is stored as the org
  secret `alert_webhook_<key>`, encrypted with `SECRETS_KEY`, and never returned. A route only
  says whether it is set.
- `kind` cannot change after creation.
- `every_hours` is 1 to 168, default 3.

`github_jobs` config:

| Field | Default | Does |
| --- | --- | --- |
| `repo` | required | `owner/name` on GitHub |
| `branch` | `main` | Branch to read |
| `path` | `README.md` | Markdown file with the table |
| `label` | `Job` | Word in the post title, such as Internship or New Grad Position |
| `skip_closed` | `true` | Leave out roles marked closed |
| `max_age_days` | `2` | Leave out rows whose Date Posted is older. 0 turns the check off |

`hackathons` config:

| Field | Default | Does |
| --- | --- | --- |
| `sources` | all three | Any of `hackclub`, `euro_hackathons`, `hackalist` |
| `min_days_ahead` | `0` | Leave out events starting sooner |
| `max_days_ahead` | `90` | Leave out events starting later |

A hackathon feed fails only when every source fails. MLH and Devpost refuse automated requests and
are not sources.

## Schedule

The `alerts.run_due` job runs every 15 minutes and runs each enabled feed whose `every_hours` has
passed since its last run, in organizations that have the module on. A failed run stores its reason
in `last_error` and is retried at the next due time.

## Moving from a standalone webhook script

1. Turn the module on for the org if it is off: `flask --app main org modules <prefix> --on alerts`.
2. Create a Discord webhook for each channel, or reuse the existing ones.
3. `PUT` one feed per source. The first run records what is listed now, so nothing is posted twice.
4. Stop the old script's schedule.
