"""RunPod REST client (api.runpod.io/v2), the runpod hosting provider and the runpod integration.

Each org uses its own API key, stored as an org secret. Godfather and hosting share it. The paths and fields
follow https://api.runpod.io/v2/openapi.json; tests/contract/fixtures/runpod_v2/ holds bodies copied from it.
"""

import math
from typing import Any
from urllib.parse import quote

import requests

from core import hosting, secrets
from core.integrations.registry import Field, Integration, IntegrationError, register
from core.log import get_logger

logger = get_logger("runpod")

BASE_URL = "https://api.runpod.io/v2"
TIMEOUT_SECONDS = 30
SECRET_NAME = "runpod_api_key"  # nosec B105 - the name of an org secret, not its value
# Manifest fields that only This server reads
SERVER_ONLY = ("publish", "volumes", "command", "workdir", "group", "alias")
# RunPod gives a persistent volume of at least this size, and only to a GPU pod
MIN_PERSISTENT_GB = 10
MIN_VCPUS = 2


class RunPodError(hosting.HostingError):
    """RunPod refused or failed a request."""


def _detail(response: requests.Response) -> str:
    """RunPod's reason for a refused request, from its error JSON or else the start of the body."""
    try:
        body = response.json()
    except ValueError:
        return response.text.strip()[:300]
    if isinstance(body, dict):
        found = body.get("error") or body.get("message") or body.get("detail") or body.get("errors")
    else:
        found = body
    if isinstance(found, list):
        found = "; ".join(str(item.get("message", item)) if isinstance(item, dict) else str(item) for item in found)
    return str(found or "")[:300]


class RunPodClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        try:
            response = requests.request(
                method,
                self._base_url + path,
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            raise RunPodError("RunPod could not be reached") from e
        if response.status_code >= 400:
            detail = _detail(response)
            logger.warning("runpod %s %s failed status=%s %s", method, path, response.status_code, detail)
            raise RunPodError(f"RunPod answered {response.status_code}: {detail}".rstrip(": "), response.status_code)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as e:
            raise RunPodError("RunPod sent a response that is not JSON") from e

    def list_pods(self) -> list[dict]:
        """Every pod on the account, from each page of GET /pods."""
        pods: list[dict] = []
        path = "/pods"
        while True:
            page = self._request("GET", path) or {}
            pods.extend(page.get("pods") or [])
            cursor = (page.get("pagination") or {}).get("nextCursor")
            if not cursor or not (page.get("pagination") or {}).get("hasNextPage"):
                return pods
            path = f"/pods?cursor={quote(str(cursor), safe='')}"

    def get_pod(self, pod_id: str) -> dict | None:
        try:
            return self._request("GET", f"/pods/{quote(pod_id, safe='')}")
        except RunPodError as e:
            if e.status == 404:
                return None
            raise

    def create_pod(self, body: dict) -> dict:
        return self._request("POST", "/pods", body)

    def update_pod(self, pod_id: str, body: dict) -> dict:
        return self._request("PATCH", f"/pods/{quote(pod_id, safe='')}", body)

    def _action(self, pod_id: str, action: str) -> Any:
        return self._request("POST", f"/pods/{quote(pod_id, safe='')}/action", {"action": action})

    def start_pod(self, pod_id: str) -> Any:
        return self._action(pod_id, "start")

    def stop_pod(self, pod_id: str) -> Any:
        return self._action(pod_id, "stop")

    def restart_pod(self, pod_id: str) -> Any:
        return self._action(pod_id, "restart")

    def delete_pod(self, pod_id: str) -> Any:
        return self._request("DELETE", f"/pods/{quote(pod_id, safe='')}")

    def gpu_types(self, cloud: str) -> list[dict]:
        """RunPod's GPU types with their pod stock for one GPU on cloud (SECURE or COMMUNITY)."""
        query = f"include=AVAILABILITY&product=POD&count=1&cloud={quote(cloud, safe='')}"
        return (self._request("GET", f"/catalog/gpus?{query}") or {}).get("gpus") or []

    def cpu_types(self) -> list[dict]:
        """RunPod's CPU flavors for pods: id, vcpu min and max, ramGbPerVcpu and price."""
        return (self._request("GET", "/catalog/cpus?product=POD") or {}).get("cpus") or []


def _power_of_two(value: float) -> int:
    """The smallest power of two at or above value, and at least MIN_VCPUS."""
    return max(MIN_VCPUS, 1 << max(0, math.ceil(value) - 1).bit_length())


def smallest_cpu(flavors: list[dict], memory_mb: int, cpus: float) -> dict:
    """The cheapest CPU pod of the catalog with at least memory_mb of memory and cpus vCPUs, as {id, vcpuCount}.

    The vCPU count is a power of two, at least 2. A flavor's memory is its ramGbPerVcpu times the vCPU count.
    Raises RunPodError when no flavor is big enough.
    """
    options = []
    for flavor in flavors:
        low, high = (flavor.get("vcpu") or {}).get("min", MIN_VCPUS), (flavor.get("vcpu") or {}).get("max", 0)
        per_vcpu_mb = float(flavor.get("ramGbPerVcpu") or 0) * 1024
        if per_vcpu_mb <= 0:
            continue
        count = _power_of_two(max(cpus, low, memory_mb / per_vcpu_mb))
        if count > high:
            continue
        price = float((flavor.get("price") or {}).get("securePerVcpu") or 0) * count
        options.append((price, count, str(flavor["id"])))
    if not options:
        # 400: the request cannot be placed, as RunPod answers a body it refuses
        raise RunPodError(f"No CPU flavor has {memory_mb} MB with {cpus} vCPUs", 400)
    _, count, flavor_id = min(options)
    return {"id": flavor_id, "vcpuCount": count}


def proxy_url(pod_id: str, port: int, path: str) -> str:
    """The public HTTPS address RunPod gives an http port of a pod."""
    return f"https://{pod_id}-{port}.proxy.runpod.net{path}"


class RunPodProvider:
    """The runpod hosting provider: pods on the org's RunPod account, with the org secret runpod_api_key."""

    name = "runpod"
    title = "RunPod"
    integration = "runpod"
    godfather = True

    def configured(self, db, org_id: int | None) -> bool:
        return org_id is not None and bool(secrets.get_secret(db, org_id, SECRET_NAME))

    def client(self, db, org_id: int | None) -> RunPodClient:
        key = secrets.get_secret(db, org_id, SECRET_NAME) if org_id is not None else None
        if not key:
            raise hosting.ProviderError(f"This organization has no RunPod API key (org secret {SECRET_NAME})", 400)
        return RunPodClient(key)

    def status(self, pod: dict | None) -> str:
        if pod is None:
            return "GONE"
        return str(pod.get("status") or "UNKNOWN")

    def pod_name(self, pod: dict) -> str | None:
        return pod.get("name")

    def machine(self, pod: dict | None) -> dict | None:
        """The pod's hardware and data center, from the v2 pod fields."""
        if not pod:
            return None
        gpu, cpu = pod.get("gpu") or {}, pod.get("cpu") or {}
        machine = {
            "gpuTypeId": gpu.get("id") if isinstance(gpu, dict) else None,
            "cpuTypeId": cpu.get("id") if isinstance(cpu, dict) else None,
            "dataCenterId": pod.get("dataCenterId"),
        }
        return {k: v for k, v in machine.items() if v} or None

    def ssh_address(self, pod: dict) -> tuple[str, int] | None:
        """(host, port) of a running pod's SSH port: ssh.direct, or the runtime port with private 22."""
        direct = (pod.get("ssh") or {}).get("direct")
        if isinstance(direct, dict) and direct.get("host") and direct.get("port"):
            return str(direct["host"]), int(direct["port"])
        runtime = pod.get("runtime") or {}
        for port in runtime.get("ports") or []:
            if port.get("private") == 22 and port.get("ip") and port.get("public"):
                return str(port["ip"]), int(port["public"])
        return None

    def proxy_url(self, pod_id: str, port: int, path: str) -> str:
        return proxy_url(pod_id, port, path)

    def healthy(self, pod_id: str, port: int, path: str | None) -> bool:
        if path is None or path == "running":
            return False
        try:
            return requests.get(proxy_url(pod_id, port, path), timeout=10).status_code < 400
        except requests.RequestException:
            return False

    def validate(self, manifest: dict) -> None:
        if "gpu" in manifest and "cpu" in manifest:
            raise hosting.HostingError("A RunPod app takes gpu or cpu, not both")
        if "path" not in manifest.get("health", {}):
            raise hosting.HostingError("A RunPod app needs a health path; tcp checks are for This server")
        used = [field for field in SERVER_ONLY if field in manifest]
        if used:
            raise hosting.HostingError(f"RunPod does not take {', '.join(used)}; those fields are for This server")
        persistent = (manifest.get("mounts") or {}).get("persistent")
        if persistent is not None and "gpu" not in manifest:
            raise hosting.HostingError("RunPod gives mounts.persistent only to a GPU pod")
        if isinstance(persistent, dict) and int(persistent.get("size") or 0) < MIN_PERSISTENT_GB:
            raise hosting.HostingError(f"RunPod needs mounts.persistent.size of at least {MIN_PERSISTENT_GB} GB")

    def request(
        self,
        app_name: str,
        org_prefix: str | None,
        pod_id: str | None,
        manifest: dict,
        image: str,
        env: dict,
        client: hosting.HostingClient | None,
    ):
        """The RunPod v2 call: POST /pods for a new pod, PATCH /pods/<id> to change one.

        A new pod with no gpu and no cpu gets the smallest CPU flavor for memory and cpus, from the catalog.
        PATCH cannot change the hardware or the mounts, so it leaves them out.
        """
        body: dict[str, Any] = {"image": image, "env": env}
        for field in ("disk", "ports", "args", "registry"):
            if field in manifest:
                body[field] = manifest[field]
        if pod_id:
            return "PATCH", f"/pods/{pod_id}", body
        body["name"] = f"{org_prefix}-{app_name}"
        for field in ("gpu", "cpu", "cloud", "dataCenterIds", "mounts"):
            if field in manifest:
                body[field] = manifest[field]
        if "gpu" not in body and "cpu" not in body:
            catalog = getattr(client, "cpu_types", None)
            if catalog is None:
                raise RunPodError("Connect RunPod first: it picks a CPU flavor for memory and cpus", 400)
            body["cpu"] = smallest_cpu(catalog(), int(manifest.get("memory") or 0), float(manifest.get("cpus") or 0))
        return "POST", "/pods", body


hosting.register(RunPodProvider())


def _test(db, org_id: int) -> str:
    key = secrets.get_secret(db, org_id, SECRET_NAME)
    if not key:
        raise IntegrationError("Set the RunPod API key first")
    try:
        pods = RunPodClient(key).list_pods()
    except RunPodError as e:
        raise IntegrationError(e.args[0]) from e
    return f"Connected. {len(pods)} pods on the account."


register(
    Integration(
        key="runpod",
        title="RunPod",
        description="Connect the org's RunPod account.",
        fields=(Field(SECRET_NAME, "API key", "RunPod > Settings > API Keys, with read and write access."),),
        docs="modules/godfather",
        test=_test,
    )
)
