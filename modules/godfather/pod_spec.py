"""The RunPod create body and recorded settings of a pod, from an officer's request, and the member setup checks."""

import posixpath
import re
import secrets as random
from typing import Any

from core.config import config
from modules.godfather import image
from modules.godfather.base import GodfatherError

# Env name prefix the pod image reads its SSH keys and setup flag from; part of the pod image contract.
POD_ENV_PREFIX = "GODFATHER_"
DEFAULT_GPU = "NVIDIA RTX A4000"
DEFAULT_CPU_FLAVOR = "cpu3c"
CLOUD_TYPES = ("COMMUNITY", "SECURE")
# RunPod v2 gives a GPU pod a persistent volume of at least this size. A CPU pod has none.
MIN_VOLUME_GB = 10
MAX_ALLOWED_USERS = 500
# Member setup: a repo to clone and a script to run in each member's folder. godfather-base 2.4.0 reads it.
MEMBER_SETUP_VERSION = "2.4.0"
MAX_SETUP_SCRIPT = 20_000
MAX_REPO_URL = 300
REPO_URL = re.compile(r"https://[A-Za-z0-9._~:/?#@!&+,;=%-]+")
REPO_NAME = re.compile(r"[A-Za-z0-9._-]+")
SETUP_NEEDS_IMAGE = f"Member setup needs godfather-base {MEMBER_SETUP_VERSION} or later"


def allowed_users(value: object) -> list[str]:
    """The sorted, unique Discord ids of a request's allowed_users. Raises GodfatherError."""
    if not isinstance(value, list) or len(value) > MAX_ALLOWED_USERS:
        raise GodfatherError(f"allowed_users must be a list of at most {MAX_ALLOWED_USERS} Discord ids")
    users = [str(v) for v in value]
    if not all(u.isdigit() and 5 <= len(u) <= 25 for u in users):
        raise GodfatherError("allowed_users must hold Discord ids")
    return sorted(set(users))


def _int(data: dict, key: str, default: int, low: int, high: int) -> int:
    value = data.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise GodfatherError(f"{key} must be a whole number from {low} to {high}")
    return value


def _text(data: dict, key: str, default: str, limit: int = 200) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise GodfatherError(f"{key} must be text of at most {limit} characters")
    return value.strip()


def member_setup(value: object) -> dict | None:
    """A pod's member setup from a request: repo, a public https git URL, and script. None when both are empty."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"repo", "script"}:
        raise GodfatherError("member_setup must be an object with repo and script")
    repo, script = value.get("repo") or "", value.get("script") or ""
    if not isinstance(repo, str) or not isinstance(script, str):
        raise GodfatherError("repo and script must be text")
    repo, script = repo.strip(), script.replace("\r\n", "\n")
    name = posixpath.basename(repo.rstrip("/")).removesuffix(".git")
    if repo and (
        len(repo) > MAX_REPO_URL or not REPO_URL.fullmatch(repo) or not REPO_NAME.fullmatch(name) or name in (".", "..")
    ):
        raise GodfatherError("repo must be a public https git URL, such as https://github.com/org/workshop.git")
    if len(script) > MAX_SETUP_SCRIPT:
        raise GodfatherError(f"script must be at most {MAX_SETUP_SCRIPT} characters")
    if not repo and not script.strip():
        return None
    return {"repo": repo, "script": script}


def setup_supported(version: str | None) -> bool:
    """True when the image runs member setup, or when the image check is off."""
    return not config.GODFATHER_MIN_IMAGE_VERSION or image.is_current(version, MEMBER_SETUP_VERSION)


def pod_request(data: dict, backend_public: str, ca_public: str, image: str) -> tuple[dict, dict]:
    """The RunPod create body and the settings recorded with the pod, from an officer's request.

    image is the default when the request names none.
    """
    cpu = bool(data.get("use_cpu_only", False))
    cloud = _text(data, "cloud_type", "COMMUNITY")
    if cloud not in CLOUD_TYPES:
        raise GodfatherError("cloud_type must be COMMUNITY or SECURE")
    env = data.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise GodfatherError("env must map names to text")
    if any(k.startswith(POD_ENV_PREFIX) for k in env):
        raise GodfatherError(f"env names starting with {POD_ENV_PREFIX} are reserved")
    volume = 0 if cpu else _int(data, "volume_in_gb", 0, 0, 2000)
    if 0 < volume < MIN_VOLUME_GB:
        raise GodfatherError(f"volume_in_gb must be 0 or from {MIN_VOLUME_GB} to 2000")
    settings = {
        "name": _text(data, "name", f"pod-{random.token_hex(4)}", 100),
        "image_name": _text(data, "image_name", image),
        "cloud_type": cloud,
        "use_cpu_only": cpu,
        "volume_in_gb": volume,
        "container_disk_in_gb": _int(data, "container_disk_in_gb", 20, 1, 500),
        "volume_mount_path": _text(data, "volume_mount_path", "/workspace"),
        "env_names": sorted(env),
    }
    setup = member_setup(data.get("member_setup"))
    if setup:
        settings["member_setup"] = setup
    body: dict[str, Any] = {
        "name": settings["name"],
        "image": settings["image_name"],
        "cloud": cloud,
        "disk": settings["container_disk_in_gb"],
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
        vcpus = _int(data, "vcpu_count", 2, 2, 64)
        if vcpus & (vcpus - 1):
            raise GodfatherError("vcpu_count must be a power of two")
        settings["vcpu_count"] = vcpus
        body["cpu"] = {"id": settings["cpu_flavor"], "vcpuCount": vcpus}
    else:
        settings["gpu_type_id"] = _text(data, "gpu_type_id", DEFAULT_GPU, 100)
        body["gpu"] = {"id": settings["gpu_type_id"], "count": 1}
        if settings["volume_in_gb"]:
            body["mounts"] = {"persistent": {"size": settings["volume_in_gb"], "path": settings["volume_mount_path"]}}
    return body, settings
