# superadmin

Routes for the platform's single superadmin (`SUPERADMIN_USER_ID`): add and remove organizations for Discord guilds, set an org's officer role, list a guild's roles, a dashboard, and the audit log across all orgs.

## Files

| File | Holds |
| --- | --- |
| `api.py` | `/check`, `/dashboard`, `/guild_roles/<guild_id>`, `/add_org/<guild_id>`, `/remove_org/<org_id>`, `/update_officer_role/<org_id>`, `/audit` |

## Surface

- Routes: `/api/superadmin`, no module switch. Every route needs the superadmin.
- Jobs: none.
- Tools: none.
- Tables: none.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
