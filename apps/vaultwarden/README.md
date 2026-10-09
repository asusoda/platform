# Vaultwarden

[Vaultwarden](https://github.com/dani-garcia/vaultwarden) is a password manager server that the Bitwarden apps use. The image is `ghcr.io/dani-garcia/vaultwarden`. The suggested tag is `1.37.4`.

> **Caution:** Vaultwarden holds the org's passwords. If the pod has no persistent volume, a deploy erases all of them. Make backups of the volume before anyone relies on it.

- Data is in `/data` on a RunPod network volume. Make the volume before you create the app.
- Use HTTPS only. The Bitwarden apps refuse plain HTTP. The RunPod proxy URL `https://<pod>-80.proxy.runpod.net` gives HTTPS.
- `SIGNUPS_ALLOWED` is `false`. Invite members from the admin page at `/admin`.
- `ADMIN_TOKEN` opens the admin page. Use an Argon2 hash from `vaultwarden hash`, not the plain token.

## Inputs

| Input | Sets |
| --- | --- |
| Admin token | `ADMIN_TOKEN`, as the org secret `app_<name>_admin_token` |
| Network volume ID | The volume at `/data` |
| Data center of the volume | `dataCenterIds` |
| Public URL (optional) | `DOMAIN`. Set it to the HTTPS URL after the first deploy, then deploy again |

## Backups

1. Stop the pod, or run `sqlite3 /data/db.sqlite3 ".backup /data/backup.sqlite3"` in its web terminal.
2. Copy `/data` (the database, `attachments/`, `sends/` and `rsa_key*`) off the volume.
3. Do a test restore to a new volume.
