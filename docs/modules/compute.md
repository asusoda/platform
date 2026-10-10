# Compute

GPU and CPU pods on an org's own RunPod account that members connect to over SSH with a compute CLI. The reference CLI is `godfather` (`pip install godfather-cli`). Officers create pods and select who can use them. A member gets a certificate for their own SSH key that works on one pod for 12 hours.

## Setup

1. Save the org's RunPod key as the org secret `runpod_api_key`. The runpod module uses the same key. `SECRETS_KEY` must be set.
2. Keep the `compute` module on for the org. It is on by default.
3. Optional: set these in the server's `.env`.
   - `COMPUTE_CLI_NAME`: the CLI name in sign-in pages and errors. Default `the compute CLI`. The example AIS server sets `godfather`.
   - `COMPUTE_POD_IMAGE`: the image of a pod when the create body has none. Default `theaisocietyasu/godfather-base:latest`.

The first pod makes two ed25519 key pairs for the org in `compute_keys`. `SECRETS_KEY` encrypts the private keys.

- `backend`: its public key goes into root's `authorized_keys` on each pod.
- `user_ca`: pods trust it through `TrustedUserCAKeys`. It signs member and officer certificates.

The pod image must do this setup. It reads `GODFATHER_SSH_PUBLIC_KEY`, `GODFATHER_SSH_CA_PUBLIC_KEY` and `GODFATHER_SETUP` from its env. It accepts certificates with the principal `gf-<pod_id>`. It has `/usr/local/bin/godfather-login`. These names do not change with `COMPUTE_CLI_NAME`.

## Officer routes

All routes are under `/api/compute/<org>` and need an officer of the org.

| Route | Does |
| --- | --- |
| `GET /pods` | Pods made here, with the live status from RunPod |
| `POST /pods` | Creates a pod. Body below. 201 |
| `GET /pods/<pod_id>` | One pod |
| `PUT /pods/<pod_id>` | `{"is_public": true}`, `{"allowed_users": ["<discord id>", ...]}`, or both |
| `POST /pods/<pod_id>/action` | `{"action": "start" \| "stop" \| "restart" \| "terminate"}`. `terminate` deletes the pod and its record |

All fields of the create body are optional:

```json
{
  "name": "workshop",
  "image_name": "theaisocietyasu/godfather-base:latest",
  "gpu_type_id": "NVIDIA RTX A4000",
  "use_cpu_only": false,
  "cpu_flavor": "cpu3c",
  "cloud_type": "COMMUNITY",
  "volume_in_gb": 1,
  "container_disk_in_gb": 2,
  "volume_mount_path": "/workspace",
  "env": {"HF_HOME": "/workspace/hf"},
  "is_public": false,
  "allowed_users": []
}
```

## Member routes

These routes need a Discord session, or the CLI token as `Authorization: Bearer plat_...`. Each request checks that the caller is a member of the org's server.

| Route | Does |
| --- | --- |
| `GET /api/compute/<org>/me/pods` | Running pods that are public or that list the member in `allowed_users` |
| `POST /api/compute/<org>/me/pods/<pod_id>/connect` | `{"public_key": "ssh-ed25519 ..."}`. Returns host, port, `user_folder` and a certificate |

A member certificate has the principal `gf-<pod_id>` and forces `/usr/local/bin/godfather-login <username>`, which puts the member in their own account and folder. An officer of the org gets a root certificate with no forced command. A certificate is valid from 5 minutes ago to 12 hours from now. The audit log records each connect.

## CLI sign-in

1. `<cli> auth` opens `GET /api/compute/<org>/cli/login`, which sends the member to Discord.
2. Discord returns to `GET /api/compute/cli/callback`. If the member is in the org's server and compute is on, the page shows a token one time.
3. The member pastes the token into the CLI. The CLI sends it on the member routes.

The token is a machine token of kind `cli` with the scope `compute:connect`, for the member's Discord id and the org. It is valid for 90 days. A new sign-in revokes the member's previous CLI token. The audit log records each token.

The CLI sign-in needs `ACCOUNTS_BASE_URL`, `CLIENT_ID` and `CLIENT_SECRET` on the server, and `<ACCOUNTS_BASE_URL>/api/compute/cli/callback` as a redirect of the Discord app.

## Sessions

A session is a time when a pod must run, such as a workshop. The `compute.schedule` job runs every 5 minutes. It starts a pod 10 minutes before a session starts, and stops it when the session ends, unless a different session on the pod is still open. A pod that was already running when its session started is also stopped after it. The job does not touch pods with no sessions. A stopped pod costs only its disk, so one pod can serve a series of workshops.

| Route | Does |
| --- | --- |
| `GET .../pods/<pod_id>/sessions` | All sessions of the pod |
| `POST .../pods/<pod_id>/sessions` | `{"title", "start_at", "stop_at"}`, ISO 8601 with a time zone, 24 hours or less. 201 |
| `DELETE .../pods/<pod_id>/sessions/<id>` | Removes a session. If the pod started for it, the next run stops it |

## File manager

These officer routes work on the files of a running pod over SFTP, as root with the org's `backend` key. Paths are absolute. `...` is `/api/compute/<org>`.

| Route | Body | Does |
| --- | --- | --- |
| `GET .../pods/<pod_id>/files?path=/workspace` | | Folder entries, folders first |
| `POST .../files/read` | `{"path"}` | Text content, up to 1 MB |
| `POST .../files/write` | `{"path", "content"}` | Replaces a file with text, up to 1 MB |
| `POST .../files/download` | `{"path"}` | The file as an attachment, up to 100 MB |
| `POST .../files/upload` | multipart `file`, form `path` (folder) | Saves a file, up to 100 MB |
| `POST .../files/mkdir` | `{"path"}` | Makes a folder |
| `POST .../files/rename` | `{"old_path", "new_path"}` | Moves or renames |
| `POST .../files/delete` | `{"path"}` | Deletes a file, or a folder and its contents. Refuses `/`, `/workspace`, `/root` and `/home` |

A stopped pod returns 409. A failed SSH connection returns 502. Platform does not check pod host keys, because RunPod does not publish them.

Officers manage pods at `/<org>/compute` and files at `/<org>/compute/<pod_id>/files` in `web/`. The dashboard Compute page shows pods and sessions.

## Limits

- Members have no web page to connect. They use the compute CLI or the routes above.
- The RunPod field names follow RunPod's REST API and are tested against a fake. Check them with a real key before you use the module in production.
