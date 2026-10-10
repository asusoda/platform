# users

Members and their org memberships. Officer routes list, show, create and update an org's members and their profile fields, and add the members of the org's Discord server.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Member routes under `/<org_prefix>` |
| `service.py` | Member lookup and create-or-update for points and storefront; the Discord member sync and role list; maps the deprecated `asu_id` and `academic_standing` keys to `student_id` and `class_standing`; merges the org's `profile_fields` |
| `models.py` | Users and org memberships |

## Surface

- Routes: `/api/users`. Routes need an officer of the org, except the index and `/<org_prefix>/submit-form`.
- Discord: `GET /<org_prefix>/discord/roles` lists the server roles. `POST /<org_prefix>/discord/sync` with `roles` (role ids; a member needs one of them; empty for everyone) and `dry_run` adds the server members to the org's members and returns `matched`, `new_users`, `joined` and `already`. A new user gets the Discord id, name and username; the username stays empty when another user has it. Bots are left out. The member list needs the Server Members intent on the bot.
- Jobs: none.
- Tools: none.
- Webhook events: `member.joined`, when `manage_user_in_organization()` adds a membership. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `users`, `user_organization_memberships`.

## Known gaps

- Views in `api.py` open their own session, query and commit. `service.py` has the lookups that points and storefront share.
- `/<org_prefix>/submit-form` is not used. See Cleanup in `docs/roadmap.md`.
