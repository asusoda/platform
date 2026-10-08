# users

Officer routes to list, view, create and update an organization's members and their profile fields.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Member routes under `/<org_prefix>` |

## Surface

- Routes: `/api/users`, no module switch. Routes need an officer of the org, except the index and `/<org_prefix>/submit-form`, which echoes its input.
- Jobs: none.
- Tools: none.
- Tables: none of its own; uses `users`, `user_organization_memberships` and `points` from `modules/points/models.py`.

## Depends on

`core.logging_config`; `modules.auth.decoraters`, `modules.points` (models, `link_or_create_user`), `modules.organizations.models`; `shared`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
