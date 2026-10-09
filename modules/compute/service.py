"""Pods an org runs on its own RunPod account for members to SSH into. No Flask here.

Officers create, share, start, stop and terminate pods. Members list the
running pods shared with them and get a short-lived certificate for their own SSH key. The org's
RunPod key is the org secret runpod_api_key, shared with the runpod apps module. The default pod
image is an org setting; without one, COMPUTE_POD_IMAGE in .env gives it.
"""

import secrets as random
from typing import Any, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

from core import secrets
from core.errors import ServiceError
from core.integrations import registry, runpod
from core.log import get_logger
from modules.auth import scopes
from modules.compute import ssh
from modules.compute.models import ComputeKey, ComputePod
from modules.organizations.models import Organization

registry.use("runpod", "compute")

logger = get_logger("compute")

BACKEND_KEY = "backend"
USER_CA_KEY = "user_ca"
# Env name prefix the pod image reads its SSH keys and setup flag from; part of the pod image contract.
POD_ENV_PREFIX = "GODFATHER_"
DEFAULT_GPU = "NVIDIA RTX A4000"
DEFAULT_CPU_FLAVOR = "cpu3c"
scopes.declare("compute:manage", "List the org's compute pods and start, stop, restart or terminate them")

ACTIONS = ("start", "stop", "restart", "terminate")
CLOUD_TYPES = ("COMMUNITY", "SECURE")
MAX_ALLOWED_USERS = 500
CONFIG_KEY = "compute"


class ComputeError(ServiceError):
    pass


def _client(db, org_id: int) -> runpod.RunPodClient:
    key = secrets.get_secret(db, org_id, runpod.SECRET_NAME)
    if not key:
        raise ComputeError("This organization has no RunPod API key (org secret runpod_api_key)", 400)
    return runpod.RunPodClient(key)


def _call(fn, *args):
    try:
        return fn(*args)
    except runpod.RunPodError as e:
        raise ComputeError(e.message, 502) from e


def keypair(db, org_id: int, kind: str) -> tuple[str, str]:
    """The org's (public, private) key pair of this kind, created on first use. Commits when created."""
    row = db.query(ComputeKey).filter_by(organization_id=org_id, kind=kind).first()
    if row is None:
        public, private = ssh.generate_keypair(f"platform-{kind}-{org_id}")
        encrypted = secrets.encrypt(private)
        if encrypted is None:
            raise ComputeError("SECRETS_KEY is not configured on this server", 503)
        db.add(ComputeKey(organization_id=org_id, kind=kind, public_key=public, private_key=encrypted))
        try:
            db.commit()
        except IntegrityError:
            # Another request created it first; use that one
            db.rollback()
        row = db.query(ComputeKey).filter_by(organization_id=org_id, kind=kind).one()
    private = secrets.decrypt(str(row.private_key))
    if private is None:
        raise ComputeError("SECRETS_KEY cannot decrypt this organization's SSH keys", 503)
    return str(row.public_key), private


def _find(db, org_id: int, pod_id: str) -> ComputePod:
    row = db.query(ComputePod).filter_by(organization_id=org_id, pod_id=pod_id).first()
    if row is None:
        raise ComputeError("Pod not found", 404)
    return row


def _status(live: dict | None) -> str:
    if live is None:
        return "GONE"
    return str(live.get("desiredStatus") or live.get("status") or "UNKNOWN")


def _pod_dict(row: ComputePod, live: dict | None) -> dict:
    return {
        "id": row.pod_id,
        "name": row.name,
        "status": _status(live),
        "is_public": bool(row.is_public),
        "allowed_users": list(cast(list, row.allowed_users) or []),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "machine": (live or {}).get("machine"),
        "cost_per_hour": (live or {}).get("costPerHr"),
    }


def list_pods(db, org_id: int, client: runpod.RunPodClient | None = None) -> list[dict]:
    """Every pod the org created here, with its live status."""
    rows = db.query(ComputePod).filter_by(organization_id=org_id).order_by(ComputePod.created_at).all()
    if not rows:
        return []
    client = client or _client(db, org_id)
    return [_pod_dict(row, _call(client.get_pod, str(row.pod_id))) for row in rows]


def get_pod(db, org_id: int, pod_id: str, client: runpod.RunPodClient | None = None) -> dict:
    row = _find(db, org_id, pod_id)
    client = client or _client(db, org_id)
    return _pod_dict(row, _call(client.get_pod, pod_id))


def _users(value: object) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_ALLOWED_USERS:
        raise ComputeError(f"allowed_users must be a list of at most {MAX_ALLOWED_USERS} Discord ids")
    users = [str(v) for v in value]
    if not all(u.isdigit() and 5 <= len(u) <= 25 for u in users):
        raise ComputeError("allowed_users must hold Discord ids")
    return sorted(set(users))


def _int(data: dict, key: str, default: int, low: int, high: int) -> int:
    value = data.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ComputeError(f"{key} must be a whole number from {low} to {high}")
    return value


def _text(data: dict, key: str, default: str, limit: int = 200) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ComputeError(f"{key} must be text of at most {limit} characters")
    return value.strip()


def pod_request(data: dict, backend_public: str, ca_public: str, image: str) -> tuple[dict, dict]:
    """The RunPod create body and the settings recorded with the pod, from an officer's request.

    image is the default when the request names none.
    """
    cpu = bool(data.get("use_cpu_only", False))
    cloud = _text(data, "cloud_type", "COMMUNITY")
    if cloud not in CLOUD_TYPES:
        raise ComputeError("cloud_type must be COMMUNITY or SECURE")
    env = data.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ComputeError("env must map names to text")
    if any(k.startswith(POD_ENV_PREFIX) for k in env):
        raise ComputeError(f"env names starting with {POD_ENV_PREFIX} are reserved")
    settings = {
        "name": _text(data, "name", f"pod-{random.token_hex(4)}", 100),
        "image_name": _text(data, "image_name", image),
        "cloud_type": cloud,
        "use_cpu_only": cpu,
        "volume_in_gb": _int(data, "volume_in_gb", 1, 0, 2000),
        "container_disk_in_gb": _int(data, "container_disk_in_gb", 2, 1, 500),
        "volume_mount_path": _text(data, "volume_mount_path", "/workspace"),
        "env_names": sorted(env),
    }
    body: dict[str, Any] = {
        "name": settings["name"],
        "imageName": settings["image_name"],
        "cloudType": cloud,
        "volumeInGb": settings["volume_in_gb"],
        "containerDiskInGb": settings["container_disk_in_gb"],
        "volumeMountPath": settings["volume_mount_path"],
        "ports": ["22/tcp"],
        "env": {
            **env,
            f"{POD_ENV_PREFIX}SSH_PUBLIC_KEY": backend_public,
            f"{POD_ENV_PREFIX}SSH_CA_PUBLIC_KEY": ca_public,
            f"{POD_ENV_PREFIX}SETUP": "true",
        },
    }
    if cpu:
        settings["cpu_flavor"] = _text(data, "cpu_flavor", DEFAULT_CPU_FLAVOR, 50)
        body["computeType"] = "CPU"
        body["cpuFlavorIds"] = [settings["cpu_flavor"]]
    else:
        settings["gpu_type_id"] = _text(data, "gpu_type_id", DEFAULT_GPU, 100)
        body["computeType"] = "GPU"
        body["gpuTypeIds"] = [settings["gpu_type_id"]]
        body["gpuCount"] = 1
    return body, settings


def _org(db, org_id: int) -> Organization:
    org = db.query(Organization).filter_by(id=org_id).first()
    if org is None:
        raise ComputeError("No such organization", 404)
    return org


def compute_settings(db, org_id: int, deployment_image: str) -> dict:
    """The org's default pod image, or None, and the deployment default it falls back to."""
    saved = (cast(dict, _org(db, org_id).config) or {}).get(CONFIG_KEY) or {}
    return {"pod_image": saved.get("pod_image"), "deployment_pod_image": deployment_image}


def pod_image(db, org_id: int, deployment_image: str) -> str:
    """The image a new pod gets when the request names none."""
    return compute_settings(db, org_id, deployment_image)["pod_image"] or deployment_image


def update_compute_settings(db, org_id: int, data: object, deployment_image: str) -> dict:
    """Set the org's default pod image. null or an empty string goes back to the deployment default. Commits."""
    if not isinstance(data, dict) or set(data) - {"pod_image"}:
        raise ComputeError("Send an object with pod_image")
    value = cast(dict, data).get("pod_image")
    if value is not None and not isinstance(value, str):
        raise ComputeError("pod_image must be a string")
    value = (value or "").strip()
    if len(value) > 200 or any(c.isspace() for c in value):
        raise ComputeError("pod_image must be an image name of at most 200 characters, with no spaces")
    org = _org(db, org_id)
    config = dict(cast(dict, org.config) or {})
    current = {k: v for k, v in (config.get(CONFIG_KEY) or {}).items() if k != "pod_image"}
    config[CONFIG_KEY] = current | ({"pod_image": value} if value else {})
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return compute_settings(db, org_id, deployment_image)


def create_pod(
    db,
    org_id: int,
    data: object,
    creator: str | None,
    image: str,
    client: runpod.RunPodClient | None = None,
) -> dict:
    """Create a pod on the org's RunPod account and record it, from image unless the request names one. Commits."""
    if not isinstance(data, dict):
        raise ComputeError("Send a JSON object")
    data = cast(dict, data)
    client = client or _client(db, org_id)
    backend_public, _ = keypair(db, org_id, BACKEND_KEY)
    ca_public, _ = keypair(db, org_id, USER_CA_KEY)
    body, settings = pod_request(data, backend_public, ca_public, image)
    allowed = _users(data.get("allowed_users", []))
    created = _call(client.create_pod, body)
    if not isinstance(created, dict) or not created.get("id"):
        raise ComputeError("RunPod did not return a pod id", 502)
    row = ComputePod(
        organization_id=org_id,
        pod_id=str(created["id"]),
        name=settings["name"],
        is_public=bool(data.get("is_public", False)),
        allowed_users=allowed,
        config=settings,
        created_by=creator,
    )
    db.add(row)
    db.commit()
    logger.info("compute pod created org=%s pod=%s by=%s", org_id, row.pod_id, creator)
    return _pod_dict(row, created)


def update_pod(db, org_id: int, pod_id: str, data: object) -> dict:
    """Change who may connect: is_public and allowed_users. Commits."""
    if not isinstance(data, dict) or not ({"is_public", "allowed_users"} & set(data)):
        raise ComputeError("Send is_public or allowed_users")
    data = cast(dict, data)
    row = _find(db, org_id, pod_id)
    if "is_public" in data:
        if not isinstance(data["is_public"], bool):
            raise ComputeError("is_public must be true or false")
        row.is_public = data["is_public"]  # type: ignore[assignment]
    if "allowed_users" in data:
        row.allowed_users = _users(data["allowed_users"])  # type: ignore[assignment]
    db.commit()
    return _pod_dict(row, None) | {"status": None}


def act(db, org_id: int, pod_id: str, action: object, client: runpod.RunPodClient | None = None) -> dict:
    """Start, stop, restart or terminate a pod. Terminate also forgets it. Commits."""
    if action not in ACTIONS:
        raise ComputeError(f"action must be one of {', '.join(ACTIONS)}")
    row = _find(db, org_id, pod_id)
    client = client or _client(db, org_id)
    if action == "start":
        _call(client.start_pod, pod_id)
    elif action == "stop":
        _call(client.stop_pod, pod_id)
    elif action == "restart":
        _call(client.stop_pod, pod_id)
        _call(client.start_pod, pod_id)
    else:
        _call(client.delete_pod, pod_id)
        from modules.compute.schedule import delete_pod_sessions

        delete_pod_sessions(db, org_id, pod_id)
        db.delete(row)
        db.commit()
    logger.info("compute pod %s org=%s pod=%s", action, org_id, pod_id)
    return {"id": pod_id, "action": action}


def member_page(directory, guild_id, query: str = "", role: str = "", limit: int = 50) -> dict:
    """Server members for the allowed members picker, sorted by name. Bots are left out.

    A query searches names through Discord. Without one, the whole member list is read. role keeps the members
    that hold that role. total counts every match; members holds the first limit.
    """
    if query:
        found = directory.search_members(guild_id, query, 100)
    else:
        found = directory.list_members(guild_id)
    matches = [m for m in found if not m.get("bot") and (not role or role in m.get("roles", []))]
    matches.sort(key=lambda m: (str(m["name"]).casefold(), m["id"]))
    return {"members": matches[:limit], "total": len(matches)}


def _may_connect(row: ComputePod, discord_id: str) -> bool:
    return bool(row.is_public) or discord_id in (cast(list, row.allowed_users) or [])


def accessible_pods(db, org_id: int, discord_id: str, client: runpod.RunPodClient | None = None) -> list[dict]:
    """Running pods this member may connect to."""
    rows = [r for r in db.query(ComputePod).filter_by(organization_id=org_id) if _may_connect(r, discord_id)]
    if not rows:
        return []
    client = client or _client(db, org_id)
    found = []
    for row in rows:
        live = _call(client.get_pod, str(row.pod_id))
        if _status(live) == "RUNNING":
            found.append({"id": row.pod_id, "name": row.name, "status": "RUNNING", "is_public": bool(row.is_public)})
    return found


def ssh_address(live: dict) -> tuple[str, int] | None:
    """(host, port) of a running pod's SSH port, from either shape RunPod reports."""
    mappings = live.get("portMappings")
    if isinstance(mappings, dict) and live.get("publicIp") and mappings.get("22"):
        return str(live["publicIp"]), int(mappings["22"])
    runtime = live.get("runtime") or {}
    for port in runtime.get("ports") or []:
        if port.get("privatePort") == 22 and port.get("ip") and port.get("isIpPublic", True):
            return str(port["ip"]), int(port.get("publicPort") or 22)
    return None


def connect(
    db,
    org_id: int,
    pod_id: str,
    discord_id: str,
    username: str,
    is_admin: bool,
    public_key: object,
    client: runpod.RunPodClient | None = None,
) -> dict:
    """SSH details and a certificate for the caller's own key. Officers get root."""
    if not ssh.is_valid_public_key(public_key):
        raise ComputeError("A valid SSH public key is required")
    row = _find(db, org_id, pod_id)
    if not is_admin and not _may_connect(row, discord_id):
        raise ComputeError("Pod not accessible", 403)
    client = client or _client(db, org_id)
    live = _call(client.get_pod, pod_id)
    if _status(live) != "RUNNING":
        raise ComputeError("Pod is not running", 409)
    address = ssh_address(cast(dict, live))
    if address is None:
        raise ComputeError("Pod network information not available", 503)
    _, ca_private = keypair(db, org_id, USER_CA_KEY)
    user = ssh.safe_username(username or discord_id)
    certificate = ssh.sign_user_key(ca_private, cast(str, public_key), pod_id, discord_id, user, is_admin)
    logger.info("compute certificate org=%s pod=%s discord_id=%s admin=%s", org_id, pod_id, discord_id, is_admin)
    return {
        "host": address[0],
        "port": address[1],
        "username": "root",
        "user_folder": user,
        "is_admin": is_admin,
        "certificate": certificate,
    }


def pod_files(db, org_id: int, pod_id: str, client: runpod.RunPodClient | None = None, opener=None):
    """An open SFTP session on a running pod, as root with the org's backend key."""
    from modules.compute.files import PodFiles

    _find(db, org_id, pod_id)
    client = client or _client(db, org_id)
    live = _call(client.get_pod, pod_id)
    if _status(live) != "RUNNING":
        raise ComputeError("Pod is not running", 409)
    address = ssh_address(cast(dict, live))
    if address is None:
        raise ComputeError("Pod network information not available", 503)
    _, backend_private = keypair(db, org_id, BACKEND_KEY)
    return (opener or PodFiles.open)(address[0], address[1], backend_private)
