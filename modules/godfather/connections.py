"""Member access to pods: the pods a member may reach, SSH certificates, connection records and root SFTP."""

import datetime
from typing import cast

from sqlalchemy.orm.attributes import flag_modified

from core import hosting, webhooks
from core.errors import ServiceError
from core.log import get_logger
from core.time import utcnow
from modules.godfather import base, ssh
from modules.godfather.models import ComputeConnection, ComputePod

logger = get_logger(__name__)

# Connections older than this are deleted when a new one is recorded.
CONNECTION_KEEP_DAYS = 90
MEMBER_CONNECTIONS = 10


def accessible_pods(db, org_id: int, discord_id: str, client: hosting.HostingClient | None = None) -> list[dict]:
    """Running pods this member may connect to."""
    rows = [r for r in db.query(ComputePod).filter_by(organization_id=org_id) if base.may_connect(r, discord_id)]
    if not rows:
        return []
    clients = base.Clients(db, org_id, client)
    found = []
    for row in rows:
        live = base.call(clients(row).get_pod, str(row.pod_id))
        if base.pod_status(live, str(row.provider)) == "RUNNING":
            found.append({"id": row.pod_id, "name": row.name, "status": "RUNNING", "is_public": bool(row.is_public)})
    return found


def member_pods(db, org_id: int, discord_id: str, client: hosting.HostingClient | None = None) -> list[dict]:
    """Every pod this member may connect to, in any state. A provider error gives the pod status UNKNOWN."""
    rows = [r for r in db.query(ComputePod).filter_by(organization_id=org_id) if base.may_connect(r, discord_id)]
    clients = base.Clients(db, org_id, client)
    pods = []
    for row in sorted(rows, key=lambda r: str(r.name)):
        try:
            status = base.pod_status(base.call(clients(row).get_pod, str(row.pod_id)), str(row.provider))
        except base.GodfatherError:
            status = "UNKNOWN"
        pods.append(
            {
                "id": row.pod_id,
                "name": row.name,
                "status": status,
                "is_public": bool(row.is_public),
                "image_current": base.image_current(row),
            }
        )
    return pods


def member_connections(db, org_id: int, discord_id: str) -> list[dict]:
    """The member's last MEMBER_CONNECTIONS certificates in this org, newest first."""
    rows = (
        db.query(ComputeConnection)
        .filter_by(organization_id=org_id, discord_id=discord_id)
        .order_by(ComputeConnection.created_at.desc(), ComputeConnection.id.desc())
        .limit(MEMBER_CONNECTIONS)
        .all()
    )
    names = {str(r.pod_id): r.name for r in db.query(ComputePod).filter_by(organization_id=org_id)}
    return [
        {
            "pod_id": row.pod_id,
            "pod_name": names.get(str(row.pod_id)),
            "is_admin": bool(row.is_admin),
            "created_at": cast(datetime.datetime, row.created_at).replace(tzinfo=datetime.UTC).isoformat(),
        }
        for row in rows
    ]


def connect(
    db,
    org_id: int,
    pod_id: str,
    discord_id: str,
    username: str,
    is_officer: bool,
    want_admin: bool,
    public_key: object,
    client: hosting.HostingClient | None = None,
) -> dict:
    """SSH details and a certificate for the caller's own key.

    Root only when the caller asks for it, is an officer, and the pod has pod admin on. Everyone else,
    officers included, gets a member certificate.
    """
    if not ssh.is_valid_public_key(public_key):
        raise base.GodfatherError("A valid SSH public key is required")
    row = base.find_pod(db, org_id, pod_id)
    if want_admin and not is_officer:
        raise base.GodfatherError("Only officers can ask for root", 403)
    if want_admin and not row.admin_enabled:
        raise base.GodfatherError("The pod owner has not turned on pod admin", 403)
    is_admin = want_admin
    if not is_officer and not base.may_connect(row, discord_id):
        raise base.GodfatherError("Pod not accessible", 403)
    if not base.image_current(row):
        raise base.GodfatherError(base.OLD_IMAGE, 409)
    client = client or base.get_client(db, org_id, str(row.provider))
    live = base.call(client.get_pod, pod_id)
    if base.pod_status(live, str(row.provider)) != "RUNNING":
        raise base.GodfatherError("Pod is not running", 409)
    address = base.ssh_address(row, live)
    _send_member_setup(db, org_id, row, address)
    _, ca_private = base.keypair(db, org_id, base.USER_CA_KEY)
    user = ssh.safe_username(username or discord_id)
    certificate = ssh.sign_user_key(ca_private, cast(str, public_key), pod_id, discord_id, user, is_admin)
    record_connection(db, org_id, pod_id, discord_id, user, is_admin)
    if is_admin:
        webhooks.emit(
            org_id,
            "pod.root_access",
            webhooks.Message(
                title=f"Root on pod {row.name}",
                fields=(("Pod", pod_id), ("Officer", user), ("Valid for", "1 hour")),
                color=webhooks.AMBER,
            ),
        )
    logger.info("godfather certificate org=%s pod=%s discord_id=%s admin=%s", org_id, pod_id, discord_id, is_admin)
    return {
        "host": address[0],
        "port": address[1],
        "username": "root",
        "user_folder": user,
        "is_admin": is_admin,
        "certificate": certificate,
    }


def _send_member_setup(db, org_id: int, row: ComputePod, address: tuple[str, int]) -> None:
    """Write the pod's member setup to the pod before a connection, so godfather-login finds the current one.

    A failure is logged and the connection goes on.
    """
    from modules.godfather.files import PodFiles

    saved = cast(dict, row.config) or {}
    setup = saved.get("member_setup")
    if not setup and not saved.get("member_setup_clear"):
        return
    _, backend_private = base.keypair(db, org_id, base.BACKEND_KEY)
    try:
        with PodFiles.open(address[0], address[1], backend_private) as pod:
            pod.put_member_setup(setup)
    except ServiceError as e:
        logger.warning("godfather member setup not sent org=%s pod=%s: %s", org_id, row.pod_id, e.message)
        return
    if not setup:
        row.config = {k: v for k, v in saved.items() if k != "member_setup_clear"}
        flag_modified(row, "config")


def pod_files(db, org_id: int, pod_id: str, client: hosting.HostingClient | None = None, opener=None):
    """An open SFTP session on a running pod, as root with the org's backend key."""
    from modules.godfather.files import PodFiles

    row = base.find_pod(db, org_id, pod_id)
    client = client or base.get_client(db, org_id, str(row.provider))
    live = base.call(client.get_pod, pod_id)
    if base.pod_status(live, str(row.provider)) != "RUNNING":
        raise base.GodfatherError("Pod is not running", 409)
    address = base.ssh_address(row, live)
    _, backend_private = base.keypair(db, org_id, base.BACKEND_KEY)
    return (opener or PodFiles.open)(address[0], address[1], backend_private)


def record_connection(db, org_id: int, pod_id: str, discord_id: str, username: str, is_admin: bool) -> None:
    """Record a certificate issued for a pod and delete the org's connections older than CONNECTION_KEEP_DAYS."""
    db.add(
        ComputeConnection(
            organization_id=org_id, pod_id=pod_id, discord_id=discord_id, username=username, is_admin=is_admin
        )
    )
    cutoff = utcnow() - datetime.timedelta(days=CONNECTION_KEEP_DAYS)
    db.query(ComputeConnection).filter(
        ComputeConnection.organization_id == org_id, ComputeConnection.created_at < cutoff
    ).delete(synchronize_session=False)
    db.commit()
