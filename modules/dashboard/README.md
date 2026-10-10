# dashboard

Read-only views for the officer dashboard in `dashboard/`: one overview of everything the org runs, and the latest GitHub Actions runs for repos the org lists. It has no tables of its own.

## Files

| File | Holds |
| --- | --- |
| `service.py` | The overview: problems, module states, activity, job runs and a section per module |
| `ci.py` | The org's repo list and the GitHub Actions runs for it, cached 120 seconds |
| `api.py` | Officer routes for the overview, branding, CI runs and the repo list |

## Routes

| Route | What it does |
| --- | --- |
| `GET /api/dashboard/<org>/overview` | Every section in one response |
| `GET /api/dashboard/<org>/ci` | Latest runs per listed repo |
| `PUT /api/dashboard/<org>/ci/repos` | Set the repo list |
| `GET /api/dashboard/<org>/branding` | The org's logo URL and accent color |
| `PUT /api/dashboard/<org>/branding` | Set the logo URL and accent color |

## Config and secrets

The repo list is `dashboard.repos` in the org config. Branding is `branding` in the org config, validated by `modules/organizations/service.py`. The optional org secret `github_token` is used for private repos.
