# organizations

Keeps the org record (Discord server, URL prefix, officer role, config) and the officer routes that set it up: module switches, calendar and LeetCode settings, org secrets, machine tokens, stats, activity and the org's audit log.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes under `/<org_id>` |
| `service.py` | `OPTIONAL_MODULES`, `module_enabled`, `set_modules`, `new_org_switches`, `branding`, `set_branding`, `find_by_prefix`, `create_organization`, org secrets and machine tokens; declares `org:read` |
| `config.py` | `OrganizationSettings`, the default config of a new org |
| `models.py` | Orgs, and the unused org config and officer tables |
| `tools.py` | The `org.*` tools: org info, branding and module switches |

## Surface

- Routes: `/api/organizations`. Each route needs an officer of the org in the URL. The list shows only the caller's orgs.
- Jobs: none.
- Tools: `org.info`, `org.branding` (scope `org:read`); `org.set_modules` (confirm), `org.set_branding` (scope `settings:write`). Tools marked confirm run only with `confirm=true`.
- Tables: `organizations`, `organization_configs`, `officers`.

Config keys: `modules` (a module name set to false for each module that is off; a new org has an entry for each optional module, on only for `NEW_ORG_MODULES` in `modules/manifest.py`), `branding` (`logo_url`, `accent_color` and `website_url`), `leetcode`, `dashboard`.

## Known gaps

- Views in `api.py` open their own session and query the org. The settings route checks the prefix in the view, not with `PREFIX_PATTERN` in `service.py`.
- `/stats`, `/activity` and `/roles` return fixed sample data.
