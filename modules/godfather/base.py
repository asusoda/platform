"""What each Godfather service file uses: the error, provider clients, the org's SSH keys and pod lookup."""

from typing import cast

from sqlalchemy.exc import IntegrityError

from core import hosting, secrets, webhooks
from core.config import config
from core.errors import ServiceError
from core.integrations import registry
from modules.godfather import image, ssh
from modules.godfather.models import ComputeKey, ComputePod

hosting.load()
registry.use("runpod", "godfather")
webhooks.declare(
    "pod.started", "Pods started", "A pod starts or restarts, by an officer, a tool or its schedule.", "godfather"
)
webhooks.declare(
    "pod.stopped", "Pods stopped", "A pod stops or is terminated, by an officer, a tool or its schedule.", "godfather"
)
webhooks.declare(
    "pod.root_access", "Root on a pod", "An officer gets a one-hour root certificate for a pod.", "godfather"
)

BACKEND_KEY = "backend"
USER_CA_KEY = "user_ca"
OLD_IMAGE = "This pod runs an old image. An officer must recreate it."


class GodfatherError(ServiceError):
    pass


def announce(org_id: int, name: str, pod_id: str, action: str, by: str) -> None:
    """Send the pod.started or pod.stopped webhook event for an action on a pod."""
    started = action in ("start", "restart", "recreate")
    verb = {
        "start": "started",
        "stop": "stopped",
        "restart": "restarted",
        "terminate": "terminated",
        "recreate": "recreated",
    }[action]
    message = webhooks.Message(
        title=f"Pod {name} {verb}",
        fields=(("Pod", pod_id), ("By", by)),
        color=webhooks.GREEN if started else webhooks.AMBER,
    )
    webhooks.emit(org_id, "pod.started" if started else "pod.stopped", message)


# Hosting providers


def get_provider(name: object) -> hosting.HostingProvider:
    """The hosting provider of this name, when it can run Godfather pods. Raises GodfatherError."""
    try:
        provider = hosting.get(name)
    except hosting.ProviderError as e:
        raise GodfatherError(e.message, e.status) from e
    if not provider.godfather:
        raise GodfatherError(f"{provider.title} cannot run Godfather pods: they need an SSH address", 400)
    return provider


def provider_of(row: ComputePod) -> hosting.HostingProvider:
    return get_provider(str(row.provider or hosting.DEFAULT))


def get_client(db, org_id: int, provider: str = hosting.DEFAULT) -> hosting.HostingClient:
    """The org's client of a provider. Raises GodfatherError when the org has no key for it."""
    try:
        return get_provider(provider).client(db, org_id)
    except hosting.ProviderError as e:
        raise GodfatherError(e.message, e.status) from e


def hosting_error(e: hosting.HostingError) -> GodfatherError:
    """A GodfatherError for a provider error: 400 when the provider refused the request, 424 when it failed."""
    status = 400 if e.status is not None and 400 <= e.status < 500 else 424
    return GodfatherError(e.message, status)


def call(fn, *args):
    """Call a provider client method. A HostingError becomes a GodfatherError."""
    try:
        return fn(*args)
    except hosting.HostingError as e:
        raise hosting_error(e) from e


class Clients:
    """One client for each provider of an org, made on first use. A given client serves every provider."""

    def __init__(self, db, org_id: int, client: hosting.HostingClient | None = None):
        self._db, self._org_id, self._client = db, org_id, client
        self._made: dict[str, hosting.HostingClient] = {}

    def __call__(self, row: ComputePod) -> hosting.HostingClient:
        if self._client is not None:
            return self._client
        name = str(row.provider or hosting.DEFAULT)
        if name not in self._made:
            self._made[name] = get_client(self._db, self._org_id, name)
        return self._made[name]


def pod_status(live: dict | None, provider: str = hosting.DEFAULT) -> str:
    return get_provider(provider).status(live)


def ssh_address(row: ComputePod, live: object) -> tuple[str, int]:
    """The SSH host and port of a running pod. Raises GodfatherError 503 when the provider has none yet."""
    provider = provider_of(row)
    address = provider.ssh_address(cast(dict, live))
    if address is None:
        raise GodfatherError(
            f"{provider.title} has not given the pod an SSH address yet. Wait a minute and try again", 503
        )
    return address


# Keys, pods and images


def keypair(db, org_id: int, kind: str) -> tuple[str, str]:
    """The org's (public, private) key pair of this kind, created on first use. Commits when created."""
    row = db.query(ComputeKey).filter_by(organization_id=org_id, kind=kind).first()
    if row is None:
        public, private = ssh.generate_keypair(f"platform-{kind}-{org_id}")
        encrypted = secrets.encrypt(private)
        if encrypted is None:
            raise GodfatherError("SECRETS_KEY is not configured on this server", 503)
        db.add(ComputeKey(organization_id=org_id, kind=kind, public_key=public, private_key=encrypted))
        try:
            db.commit()
        except IntegrityError:
            # Another request created it first; use that one
            db.rollback()
        row = db.query(ComputeKey).filter_by(organization_id=org_id, kind=kind).one()
    private = secrets.decrypt(str(row.private_key))
    if private is None:
        raise GodfatherError("SECRETS_KEY cannot decrypt this organization's SSH keys", 503)
    return str(row.public_key), private


# The pod id of a row whose create request still waits for the provider
PENDING_PREFIX = "pending-"


def pending(row: ComputePod) -> bool:
    """Whether the row holds a create request that the provider has not answered yet."""
    return str(row.pod_id).startswith(PENDING_PREFIX)


def find_pod(db, org_id: int, pod_id: str) -> ComputePod:
    row = db.query(ComputePod).filter_by(organization_id=org_id, pod_id=pod_id).first()
    if row is None:
        raise GodfatherError("Pod not found", 404)
    if pending(row):
        raise GodfatherError("The pod is still being created. Try again in a minute", 409)
    return row


def may_connect(row: ComputePod, discord_id: str) -> bool:
    """Whether a member may connect to a pod: it is public, or the member is in its allowed users."""
    return bool(row.is_public) or discord_id in (cast(list, row.allowed_users) or [])


def image_current(row: ComputePod) -> bool:
    """True when the pod was created from godfather-base at or above GODFATHER_MIN_IMAGE_VERSION."""
    return image.is_current(row.image_version, config.GODFATHER_MIN_IMAGE_VERSION)


def checked_image(reference: str) -> image.ImageInfo | None:
    """The resolved image when the check is on, None when GODFATHER_MIN_IMAGE_VERSION is empty."""
    minimum = config.GODFATHER_MIN_IMAGE_VERSION
    if not minimum:
        return None
    info = image.resolve(reference)
    image.check(info, minimum)
    return info
