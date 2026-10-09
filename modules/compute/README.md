# compute

Runs GPU and CPU pods on an org's own RunPod account that members connect to over SSH. Officers create, share, start, stop and schedule pods and manage their files. Members get a short-lived SSH certificate from the compute CLI.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes under `/<org_prefix>/pods` and the member list and search at `/<org_prefix>/members` and `/<org_prefix>/members/roles`, member routes under `/<org_prefix>/me`, and the CLI sign-in through Discord |
| `tools.py` | The `compute.*` tools for agents |
| `service.py` | Pods on RunPod, sharing and member connect; reads the org secret `runpod_api_key` |
| `ssh.py` | The org's SSH keys and short-lived certificates |
| `files.py` | File operations on a pod over SFTP, as root with the org's backend key |
| `schedule.py` | Sessions: start a pod before a session and stop it after |
| `cli_login.py` | The CLI machine token (kind `cli`, scope `compute:connect`) for a member |
| `models.py`, `jobs.py` | Pods, SSH keys and sessions; the schedule job |

## Surface

- Routes: `/api/compute`, behind the `compute` switch. Officer routes need an officer of the org. Member routes need a Discord session or a CLI token with `compute:connect`.
- Jobs: `compute.schedule`, schedule `*/5 * * * *`.
- Tools: `compute.pods` and `compute.pod_action` (confirm), scope `compute:manage`. Tools marked confirm run only with `confirm=true`.
- Tables: `compute_pods`, `compute_keys`, `compute_sessions`.

See [docs/modules/compute.md](../../docs/modules/compute.md) for setup, `COMPUTE_CLI_NAME`, `COMPUTE_POD_IMAGE`, the org default pod image and the pod image contract.
