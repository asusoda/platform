# Compute pods (compute module)

GPU and CPU pods on an org's own RunPod account that members SSH into with a compute CLI. The
reference CLI is `godfather` (`pip install godfather-cli`).
Officers create pods and choose who may use them. Members get a certificate for their own SSH key
that works on one pod for twelve hours.

## Setup

1. Store the org's RunPod key as the org secret `runpod_api_key` (the same key the runpod apps
   module uses). `SECRETS_KEY` must be set on the server.
2. Leave the `compute` module on for the org (it is on unless turned off).
3. Optionally set, in the server's `.env`:
   - `COMPUTE_CLI_NAME`: the CLI name in sign-in pages and errors ("Run <name> auth again").
     Defaults to `the compute CLI`. AIS sets `COMPUTE_CLI_NAME=godfather`.
   - `COMPUTE_POD_IMAGE`: the image a pod uses when the create body names none. Defaults to
     `theaisocietyasu/godfather-base:latest`, the reference image for the pod contract below.

The first pod creates two ed25519 key pairs for the org, stored in `compute_keys` with the private
halves encrypted by `SECRETS_KEY`:

- `backend`: its public key goes into root's authorized_keys on every pod.
- `user_ca`: pods trust it through TrustedUserCAKeys; it signs member and officer certificates.

Pods use `COMPUTE_POD_IMAGE` by default. The pod contract: the image reads
`GODFATHER_SSH_PUBLIC_KEY`, `GODFATHER_SSH_CA_PUBLIC_KEY` and `GODFATHER_SETUP` from its env, so
those names are reserved; it accepts certificates with principal `gf-<pod_id>`; and it provides
`/usr/local/bin/godfather-login`. These names are fixed whatever `COMPUTE_CLI_NAME` is. A different
image must do the same setup to accept certificates.

## Officer routes

Officer access, like other org routes. `<org>` is the org prefix.

| Route | What it does |
|-------|--------------|
| `GET /api/compute/<org>/pods` | Pods created here, with live status from RunPod |
| `POST /api/compute/<org>/pods` | Create a pod. Body below. 201 |
| `GET /api/compute/<org>/pods/<pod_id>` | One pod |
| `PUT /api/compute/<org>/pods/<pod_id>` | `{"is_public": true}` and/or `{"allowed_users": ["<discord id>", ...]}` |
| `POST /api/compute/<org>/pods/<pod_id>/action` | `{"action": "start" \| "stop" \| "restart" \| "terminate"}`. Terminate deletes the pod and its record |

Create body, every field optional:

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

Discord login session and membership of the org's server, like other member routes. The compute
CLI sends `Authorization: Bearer plat_...` instead (see CLI sign-in below); membership is checked on
every request the same way.

| Route | What it does |
|-------|--------------|
| `GET /api/compute/<org>/me/pods` | Running pods that are public or list the member in allowed_users |
| `POST /api/compute/<org>/me/pods/<pod_id>/connect` | `{"public_key": "ssh-ed25519 ..."}`. Returns host, port, user_folder and a certificate |

A member certificate has principal `gf-<pod_id>` and forces `/usr/local/bin/godfather-login
<username>`, which puts the member in their own account and folder. Officers of the org get a root
certificate without the forced command. Each certificate is valid from five minutes ago to twelve
hours from now. Every connect is in the audit log.

## CLI sign-in

The compute CLI gets its credential from a browser sign-in:

1. `<cli> auth` (`godfather auth` for the reference CLI) opens `GET /api/compute/<org>/cli/login`, which sends the member to Discord.
2. Discord returns to `GET /api/compute/cli/callback`. If the member is in the org's server and
   compute is on, the page shows a token once.
3. The member pastes it into the CLI, which sends it as a bearer token on the member routes.

The token is a machine token of kind `cli` with scope `compute:connect`, bound to the member's
Discord id and the org, valid for 90 days. Signing in again revokes the member's previous CLI token.
Each token issued is in the audit log.

Setup: `ACCOUNTS_BASE_URL`, `CLIENT_ID` and `CLIENT_SECRET` set on the server, and
`<ACCOUNTS_BASE_URL>/api/compute/cli/callback` added as a redirect on the Discord application.

## Sessions

A session is a window when a pod should run, such as a workshop. The `compute.schedule` job runs
every five minutes. It starts a pod ten minutes before a session begins and stops it when the
session ends, unless another session on the same pod is still running. A pod already running when
its session begins is also stopped afterwards. Pods without sessions are never touched by the job.
Between sessions a stopped pod bills only for its disk, so one pod can serve a whole workshop
series.

| Route | What it does |
|-------|--------------|
| `GET /api/compute/<org>/pods/<pod_id>/sessions` | Every session of the pod |
| `POST /api/compute/<org>/pods/<pod_id>/sessions` | `{"title", "start_at", "stop_at"}`, ISO 8601 with a timezone. At most 24 hours. 201 |
| `DELETE /api/compute/<org>/pods/<pod_id>/sessions/<id>` | Remove a session. A pod already started for it is stopped at the next run |

## Web pages

Officers manage pods at `/<org>/compute` (create, start, stop, restart, terminate, who may
connect, sessions) and a running pod's files at `/<org>/compute/<pod_id>/files` (browse, edit text, upload,
download, new folder, rename, delete). Both are hidden when the module is off.

## File manager

Officer routes that work on a running pod's files over SFTP, as root with the org's `backend` key.
Paths are absolute and normalized.

| Route | Body | What it does |
|-------|------|--------------|
| `GET .../pods/<pod_id>/files?path=/workspace` | | Directory entries, directories first |
| `POST .../files/read` | `{"path"}` | Text content, up to 1 MB |
| `POST .../files/write` | `{"path", "content"}` | Replace a file with text, up to 1 MB |
| `POST .../files/download` | `{"path"}` | The file as an attachment, up to 100 MB |
| `POST .../files/upload` | multipart `file`, form `path` (directory) | Store a file, up to 100 MB |
| `POST .../files/mkdir` | `{"path"}` | Create a directory |
| `POST .../files/rename` | `{"old_path", "new_path"}` | Move or rename |
| `POST .../files/delete` | `{"path"}` | Delete a file or a directory with its contents. Refuses `/`, `/workspace`, `/root`, `/home` |

`...` is `/api/compute/<org>`. A stopped pod returns 409; a failed SSH connection returns 502.
Pod host keys are not checked, since RunPod publishes none.

## Not ported yet

- A member page for connecting. Members use the compute CLI or the routes above.
- The RunPod request and response field names follow RunPod's REST API and are checked against a
  fake in the tests, not against RunPod itself. Check them with a real key before the cutover.
