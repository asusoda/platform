# superadmin

Routes for the one superadmin of the deployment (`SYS_ADMIN`): add and remove orgs for Discord servers, set an org's officer role, list a server's roles, and read the audit log of all orgs.

## Files

| File | Holds |
| --- | --- |
| `api.py` | `/check`, `/dashboard`, `/guild_roles/<guild_id>`, `/add_org/<guild_id>`, `/remove_org/<org_id>`, `/update_officer_role/<org_id>`, `/audit` |
| `service.py` | The superadmin check, servers with no org, an officer's orgs, server roles, role checks and new orgs |

## Surface

- Routes: `/api/superadmin`. Each route needs the superadmin.
- Jobs: none.
- Tools: none.
- Tables: none.

## Known gaps

- `/add_org` makes the org with `service.new_organization`, not with `organizations.service.create_organization`. A taken prefix is not checked.
- `/remove_org` deletes the org row with no cascade.
