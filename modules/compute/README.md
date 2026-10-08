# compute

Runs GPU and CPU pods on the organization's own RunPod account for members to SSH into. Officers create, share, start, stop and schedule pods and manage files on them; members list the pods shared with them and get a short-lived SSH certificate, from the web app or the `godfather` CLI.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes under `/<org_prefix>/pods`, member routes under `/<org_prefix>/me`, and the CLI sign-in through Discord |
| `service.py` | Pod lifecycle on RunPod, sharing, member connect; reads the org secret `runpod_api_key` |
| `ssh.py` | The org's SSH keys and short-lived user certificates |
| `files.py` | File operations on a pod over SFTP, as root with the org's backend key |
| `schedule.py` | Pod sessions: start a pod before a session and stop it after |
| `cli_login.py` | The CLI machine token (kind `cli`, scope `compute:connect`) for a member |
| `models.py` | Pods, SSH keys, sessions |
| `jobs.py` | The schedule job |

## Surface

- Routes: `/api/compute`, gated by the `compute` switch. Officer routes need an officer of the org; member routes take a Discord session or a `godfather` CLI token with `compute:connect`.
- Jobs: `compute.schedule`, cron `*/5 * * * *`.
- Tools: none.
- Tables: `compute_pods`, `compute_keys`, `compute_sessions`.

## Depends on

`core.runpod`, `core.secrets`, `core.audit`, `core.errors`, `core.jobs`, `core.logging_config`, `core.base`; `modules.auth` (decorators, access, machine tokens, models, scopes), `modules.accounts.providers` (Discord consent), `modules.organizations`; `shared`.

## More

[docs/compute.md](../../docs/compute.md)
