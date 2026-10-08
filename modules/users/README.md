# users

Members and their org memberships. Officer routes list, view, create and update an org's members and their profile fields.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Member routes under `/<org_prefix>` |
| `service.py` | Member lookup and upsert (`manage_user_in_organization`, `get_or_create_user`, `link_or_create_user`, `get_or_create_user_from_clerk`) that points and storefront use; the helpers that map the deprecated `asu_id` and `academic_standing` keys to `student_id` and `class_standing` and merge per-org `profile_fields` |
| `models.py` | Users and org memberships (with the org's `profile_fields`) |

## Surface

- Routes: `/api/users`, no module switch. Routes need an officer of the org, except the index and `/<org_prefix>/submit-form`, which echoes its input.
- Jobs: none.
- Tools: none.
- Tables: `users`, `user_organization_memberships`. Reads `points` from `modules/points/models.py`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
