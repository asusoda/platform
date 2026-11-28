# feeds.jobs

Software internship and new grad roles from GitHub job lists. It is shared: one list of presets for every org.

## Files

| File | Holds |
| --- | --- |
| `__init__.py` | `SUBMODULE` (`shared=True`) and `FEEDS`: the `internships` and `new-grad` presets |

## Surface

- Switch: `feeds.jobs`. Feeds of kind `github_jobs` run only while it is on, and its presets show on the Job alerts page. Turning it on writes the org's `submodule_subscriptions` row.
- Migration `c5e7a9b1d3f4` turned it on for each org that subscribed to `careers` or had a `github_jobs` feed.

The kind's code is `modules/feeds/github_jobs.py`.
