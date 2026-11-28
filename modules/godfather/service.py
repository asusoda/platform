"""Officer actions on Godfather pods: list, create, recreate, share, start, stop and terminate. No Flask here.

Pods run on an org's own hosting provider account for members to SSH into. Each pod keeps the name of its
provider (core.hosting). Only RunPod gives pods an SSH address, with the org secret runpod_api_key, shared
with the runpod apps module. The default pod image is an org setting (settings.py); without one,
GODFATHER_POD_IMAGE in .env gives it. The other files of the service:

- base.py: GodfatherError, provider clients, the org's SSH keys and pod lookup
- pod_spec.py: the create body and settings of a pod, and the member setup checks
- settings.py: the org's default pod image
- connections.py: the pods a member may reach, SSH certificates and root SFTP
- members.py: who may connect, who got a certificate and who is connected now
- gpu_stock.py: GPU stock and prices
- schedule.py: sessions that start and stop a pod
"""

from typing import cast

from sqlalchemy.orm.attributes import flag_modified

from core import hosting, limits
from core.config import config
from core.log import get_logger
from core.time import utcnow
from modules.auth import scopes
from modules.godfather import base
from modules.godfather.models import ComputeConnection, ComputePod, ComputeSession
from modules.godfather.pod_spec import SETUP_NEEDS_IMAGE, allowed_users, member_setup, pod_request, setup_supported

logger = get_logger("godfather")

scopes.declare(
    "godfather:manage",
    "Create, list and change the org's Godfather pods, their sessions, files and settings; start, stop, restart or "
    "terminate them",
    uses=("runpod",),
)

ACTIONS = ("start", "stop", "restart", "terminate", "recreate")

PODS_LIMIT = "godfather.pods"
limits.declare(
    PODS_LIMIT,
    "godfather",
    "Pods",
    10,
    unit="pods",
    usage=lambda db, org_id: db.query(ComputePod).filter_by(organization_id=org_id).count(),
)


def _pod_dict(row: ComputePod, live: dict | None) -> dict:
    provider = base.provider_of(row)
    return {
        "id": row.pod_id,
        "name": row.name,
        "provider": provider.name,
        "status": provider.status(live),
        "is_public": bool(row.is_public),
        "allowed_users": list(cast(list, row.allowed_users) or []),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "machine": provider.machine(live),
        "cost_per_hour": (live or {}).get("cost", (live or {}).get("costPerHr")),
        "image": (cast(dict, row.config) or {}).get("image_name"),
        "image_version": row.image_version,
        "image_current": base.image_current(row),
        "admin_enabled": bool(row.admin_enabled),
        "admin_enabled_by": row.admin_enabled_by,
        "owner": row.created_by,
        "member_setup": (cast(dict, row.config) or {}).get("member_setup"),
    }


def list_pods(db, org_id: int, client: hosting.HostingClient | None = None) -> list[dict]:
    """Every pod the org created here, with its live status from its provider."""
    rows = db.query(ComputePod).filter_by(organization_id=org_id).order_by(ComputePod.created_at).all()
    clients = base.Clients(db, org_id, client)
    return [_pod_dict(row, base.call(clients(row).get_pod, str(row.pod_id))) for row in rows]


def get_pod(db, org_id: int, pod_id: str, client: hosting.HostingClient | None = None) -> dict:
    row = base.find_pod(db, org_id, pod_id)
    client = client or base.get_client(db, org_id, str(row.provider))
    return _pod_dict(row, base.call(client.get_pod, pod_id))


def create_pod(
    db,
    org_id: int,
    data: object,
    creator: str | None,
    image: str,
    client: hosting.HostingClient | None = None,
) -> dict:
    """Create a pod on the org's provider account and record it, from image unless the request names one. Commits.

    provider names the hosting provider, runpod when missing. The create body follows the RunPod v2 API.
    """
    if not isinstance(data, dict):
        raise base.GodfatherError("Send a JSON object")
    data = cast(dict, data)
    limits.check(db, org_id, PODS_LIMIT)
    provider = base.get_provider(data.get("provider", hosting.DEFAULT))
    client = client or base.get_client(db, org_id, provider.name)
    allowed = allowed_users(data.get("allowed_users", []))
    row, created = _create(db, org_id, provider, client, data, image)
    row.is_public = bool(data.get("is_public", False))
    row.allowed_users = allowed
    row.created_by = creator
    db.add(row)
    db.commit()
    logger.info("Godfather pod created org=%s pod=%s by=%s", org_id, row.pod_id, creator)
    return _pod_dict(row, created)


def _create(
    db, org_id: int, provider: hosting.HostingProvider, client: hosting.HostingClient, data: dict, default_image: str
) -> tuple[ComputePod, dict]:
    """Check the image, create the pod on the provider pinned to the image digest, and return a new row."""
    backend_public, _ = base.keypair(db, org_id, base.BACKEND_KEY)
    ca_public, _ = base.keypair(db, org_id, base.USER_CA_KEY)
    body, settings = pod_request(data, backend_public, ca_public, default_image)
    info = base.checked_image(settings["image_name"])
    if settings.get("member_setup") and info is not None and not setup_supported(info.version):
        raise base.GodfatherError(f"{SETUP_NEEDS_IMAGE}. Pick a newer image.", 422)
    if info is not None:
        body["image"] = info.reference
        settings["image_digest"] = info.digest
    created = base.call(client.create_pod, body)
    if not isinstance(created, dict) or not created.get("id"):
        raise base.GodfatherError(f"{provider.title} did not return a pod id", 424)
    row = ComputePod(
        organization_id=org_id,
        pod_id=str(created["id"]),
        provider=provider.name,
        name=settings["name"],
        config=settings,
        image_digest=info.digest if info else None,
        image_version=info.version if info else None,
    )
    return row, created


# The settings of a pod that a recreate sends again. Env values are not stored, so env is not copied.
RECREATE_KEYS = (
    "name",
    "cloud_type",
    "use_cpu_only",
    "volume_in_gb",
    "container_disk_in_gb",
    "volume_mount_path",
    "cpu_flavor",
    "vcpu_count",
    "gpu_type_id",
    "member_setup",
)


def recreate(db, org_id: int, pod_id: str, default_image: str, client: hosting.HostingClient | None = None) -> dict:
    """Replace a pod with a new one from the default image. The old pod and its disk are deleted. Commits.

    The new pod keeps the name, sharing, owner and sessions. Pod admin starts off. Env values are not kept.
    """
    old = base.find_pod(db, org_id, pod_id)
    provider = base.provider_of(old)
    client = client or base.get_client(db, org_id, provider.name)
    saved = cast(dict, old.config) or {}
    data = {k: saved[k] for k in RECREATE_KEYS if k in saved}
    row, created = _create(db, org_id, provider, client, data, default_image)
    row.is_public = bool(old.is_public)
    row.allowed_users = list(cast(list, old.allowed_users) or [])
    row.created_by = old.created_by
    db.add(row)
    db.query(ComputeSession).filter_by(organization_id=org_id, pod_id=pod_id).update(
        {"pod_id": row.pod_id}, synchronize_session=False
    )
    db.query(ComputeConnection).filter_by(organization_id=org_id, pod_id=pod_id).delete()
    db.delete(old)
    db.commit()
    try:
        client.delete_pod(pod_id)
    except hosting.HostingError as e:
        if e.status != 404:
            logger.warning("Godfather recreate left the old pod org=%s pod=%s: %s", org_id, pod_id, e.message)
    logger.info("Godfather pod recreated org=%s old=%s new=%s", org_id, pod_id, row.pod_id)
    base.announce(org_id, str(row.name), str(row.pod_id), "recreate", "an officer or a tool")
    return {"id": row.pod_id, "replaced": pod_id, "env_not_copied": list(saved.get("env_names") or [])}


def set_pod_admin(db, org_id: int, pod_id: str, enabled: object, caller: str | None, is_superadmin: bool) -> dict:
    """Turn pod admin on or off. Only the pod owner or the superadmin may. Commits."""
    if not isinstance(enabled, bool):
        raise base.GodfatherError("enabled must be true or false")
    row = base.find_pod(db, org_id, pod_id)
    if not is_superadmin and (caller is None or caller != row.created_by):
        raise base.GodfatherError("Only the pod owner can change pod admin", 403)
    row.admin_enabled = enabled
    row.admin_enabled_by = caller if enabled else None
    row.admin_enabled_at = utcnow() if enabled else None
    db.commit()
    logger.info("Godfather pod admin org=%s pod=%s enabled=%s by=%s", org_id, pod_id, enabled, caller)
    return _pod_dict(row, None) | {"status": None}


def update_pod(db, org_id: int, pod_id: str, data: object) -> dict:
    """Change who may connect (is_public, allowed_users) and the member setup. Commits.

    The pod gets a changed member setup on the next member connection.
    """
    if not isinstance(data, dict) or not ({"is_public", "allowed_users", "member_setup"} & set(data)):
        raise base.GodfatherError("Send is_public, allowed_users or member_setup")
    data = cast(dict, data)
    row = base.find_pod(db, org_id, pod_id)
    if "is_public" in data:
        if not isinstance(data["is_public"], bool):
            raise base.GodfatherError("is_public must be true or false")
        row.is_public = data["is_public"]
    if "allowed_users" in data:
        row.allowed_users = allowed_users(data["allowed_users"])
    if "member_setup" in data:
        setup = member_setup(data["member_setup"])
        if setup and not setup_supported(row.image_version):
            raise base.GodfatherError(f"{SETUP_NEEDS_IMAGE}. Recreate the pod first.", 422)
        saved = {k: v for k, v in (cast(dict, row.config) or {}).items() if k != "member_setup"}
        # member_setup_clear asks the next connection to remove the files from the pod
        saved |= {"member_setup": setup} if setup else {"member_setup_clear": True}
        row.config = saved
        flag_modified(row, "config")
    db.commit()
    return _pod_dict(row, None) | {"status": None}


def act(
    db,
    org_id: int,
    pod_id: str,
    action: object,
    client: hosting.HostingClient | None = None,
    default_image: str | None = None,
) -> dict:
    """Start, stop, restart, terminate or recreate a pod. Terminate also forgets it. Commits."""
    if action not in ACTIONS:
        raise base.GodfatherError(f"action must be one of {', '.join(ACTIONS)}")
    if action == "recreate":
        return recreate(db, org_id, pod_id, default_image or config.GODFATHER_POD_IMAGE, client)
    row = base.find_pod(db, org_id, pod_id)
    name = str(row.name)
    client = client or base.get_client(db, org_id, str(row.provider))
    if action == "start":
        base.call(client.start_pod, pod_id)
    elif action == "stop":
        base.call(client.stop_pod, pod_id)
    elif action == "restart":
        base.call(client.stop_pod, pod_id)
        base.call(client.start_pod, pod_id)
    else:
        try:
            client.delete_pod(pod_id)
        except hosting.HostingError as e:
            # A pod already deleted on the provider is forgotten here too
            if e.status != 404:
                raise base.hosting_error(e) from e
            logger.info("Godfather pod already gone on %s org=%s pod=%s", row.provider, org_id, pod_id)
        from modules.godfather.schedule import delete_pod_sessions

        delete_pod_sessions(db, org_id, pod_id)
        db.query(ComputeConnection).filter_by(organization_id=org_id, pod_id=pod_id).delete()
        db.delete(row)
        db.commit()
    logger.info("Godfather pod %s org=%s pod=%s", action, org_id, pod_id)
    base.announce(org_id, name, pod_id, str(action), "an officer or a tool")
    return {"id": pod_id, "action": action}
