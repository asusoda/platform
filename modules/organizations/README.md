# organizations

Holds the organization record (Discord guild, URL prefix, officer role, settings) and the officer routes that configure it: module switches, calendar and LeetCode settings, org secrets, machine tokens, stats, activity and the org's audit log.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes under `/<org_id>` |
| `service.py` | `OPTIONAL_MODULES`, `module_enabled`, `set_modules`, `branding`, `set_branding`, `find_by_prefix`, `create_organization`, and the org's secrets and machine tokens; declares the `org:read` scope |
| `config.py` | `OrganizationSettings`, the default settings written into a new org's config |
| `models.py` | Organizations, org config rows, officers |
| `tools.py` | The `org.info` tool |

## Surface

- Routes: `/api/organizations`, no module switch. Every route needs a signed-in officer of the org in the URL; the list shows only orgs the caller is an officer of.
- Jobs: none.
- Tools: `org.info` (scope `org:read`).
- Tables: `organizations`, `organization_configs`, `officers`.

## Config keys

- `modules`: module name to false for each module turned off.
- `branding`: `logo_url` (https) and `accent_color` (`#RRGGBB`), shown by the officer dashboard and set through `/api/dashboard/<org>/branding`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
