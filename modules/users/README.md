# users

Members and their org memberships. Officer routes list, show, create and update an org's members and their profile fields.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Member routes under `/<org_prefix>` |
| `service.py` | Member lookup and create-or-update for points and storefront; maps the deprecated `asu_id` and `academic_standing` keys to `student_id` and `class_standing`; merges the org's `profile_fields` |
| `models.py` | Users and org memberships |

## Surface

- Routes: `/api/users`. Routes need an officer of the org, except the index and `/<org_prefix>/submit-form`.
- Jobs: none.
- Tools: none.
- Tables: `users`, `user_organization_memberships`.

## Known gaps

- Views in `api.py` open their own session, query and commit. `service.py` has the lookups that points and storefront share.
- `/<org_prefix>/submit-form` is not used. See Cleanup in `docs/roadmap.md`.
