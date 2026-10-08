# points

Tracks an organization's members and the points they earn. Officers add members, award points by hand or from an event attendance CSV, and read the leaderboard; members sign in with Clerk to see their profile.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Member and points routes, CSV upload, leaderboard, member login and profile; also the user helpers (`get_or_create_user`, `link_or_create_user`, `get_or_create_user_from_clerk`) that users and storefront import |
| `service.py` | The leaderboard query; the member field helpers that map the deprecated `asu_id` and `academic_standing` keys to `student_id` and `class_standing` and merge per-org `profile_fields`; declares the `points:read` scope |
| `models.py` | Users, org memberships (with the org's `profile_fields`), point entries |
| `tools.py` | The `points.leaderboard` tool |
| `jobs.py` | The CSV import job |

## Surface

- Routes: `/api/points`, gated by the `points` switch. Most routes need an officer of the org; `/<org_prefix>/leaderboard` is open and shows emails only to a signed-in caller; `/member_login` takes a Clerk token and `/member_profile` reads the session it sets.
- Jobs: `points.import_event_csv`, deferred by the CSV upload, no schedule.
- Tools: `points.leaderboard` (scope `points:read`, gated by `points`).
- Tables: `users`, `user_organization_memberships`, `points`.

## Depends on

`core.clerk_auth`, `core.jobs`, `core.tools`, `core.logging_config`, `core.base`; `modules.auth` (decorators, access, scopes), `modules.organizations.models`; `shared` (`db_connect`, `tokenManager`).

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
