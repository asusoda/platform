"""Checks that a pod image is godfather-base at a minimum version, from its registry labels. No Flask here.

resolve() reads the image from its registry with the OCI distribution API and an anonymous token, so
the image must be public. An image built FROM godfather-base keeps the version label and passes.
"""

import dataclasses
import re

import requests

from core import net
from core.cache import cache
from core.errors import ServiceError

# The label godfather-base sets from its VERSION file; part of the pod image contract.
VERSION_LABEL = "com.ais-asu.godfather.base-version"
DOCKER_HUB = "registry-1.docker.io"
TIMEOUT = 10
CACHE_SECONDS = 600
MANIFEST_TYPES = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)
INDEX_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
)
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
REFERENCE_RE = re.compile(r"^[a-z0-9]+([._/-][a-z0-9]+)*$")


class ImageError(ServiceError):
    def __init__(self, message: str):
        super().__init__(message, 422)


@dataclasses.dataclass(frozen=True)
class Reference:
    registry: str
    repository: str
    tag: str
    digest: str | None

    def pinned(self, digest: str) -> str:
        """The reference by digest, which RunPod pulls as is."""
        host = "" if self.registry == DOCKER_HUB else f"{self.registry}/"
        return f"{host}{self.repository}@{digest}"


@dataclasses.dataclass(frozen=True)
class ImageInfo:
    reference: str
    digest: str
    version: str | None


def parse(reference: str) -> Reference:
    """Split registry, repository, tag and digest. Docker Hub names get registry-1.docker.io and library/."""
    name, _, digest_part = reference.partition("@")
    digest = digest_part or None
    tag = "latest"
    last = name.rsplit("/", 1)[-1]
    if ":" in last:
        name, tag = name.rsplit(":", 1)
    first, _, rest = name.partition("/")
    if rest and ("." in first or ":" in first or first == "localhost"):
        registry, repository = first, rest
    else:
        registry, repository = DOCKER_HUB, name
    if registry == DOCKER_HUB and "/" not in repository:
        repository = f"library/{repository}"
    if registry == "docker.io":
        registry = DOCKER_HUB
    if not REFERENCE_RE.match(repository) or not tag or (digest is not None and not digest.startswith("sha256:")):
        raise ImageError(f"{reference} is not an image reference")
    return Reference(registry, repository, tag, digest)


def version_tuple(version: str | None) -> tuple[int, int, int] | None:
    match = VERSION_RE.match(version or "")
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def is_current(version: str | None, minimum: str) -> bool:
    """True when version is at or above minimum. An empty minimum turns the check off."""
    if not minimum:
        return True
    have, need = version_tuple(version), version_tuple(minimum)
    return have is not None and need is not None and have >= need


def _token(response: requests.Response, ref: Reference) -> str | None:
    """An anonymous pull token from a 401 Bearer challenge."""
    challenge = response.headers.get("WWW-Authenticate", "")
    if not challenge.lower().startswith("bearer "):
        return None
    params = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
    if "realm" not in params:
        return None
    query = {"service": params.get("service", ""), "scope": f"repository:{ref.repository}:pull"}
    answer = net.get(params["realm"], params=query, timeout=TIMEOUT, allow_redirects=False)
    if answer.status_code != 200:
        return None
    body = answer.json()
    return body.get("token") or body.get("access_token")


def _get(url: str, ref: Reference, accept: str, token: list[str | None]) -> requests.Response:
    headers = {"Accept": accept}
    if token[0]:
        headers["Authorization"] = f"Bearer {token[0]}"
    response = net.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=False)
    if response.status_code == 401 and not token[0]:
        token[0] = _token(response, ref)
        if token[0]:
            headers["Authorization"] = f"Bearer {token[0]}"
            response = net.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=False)
    return response


def _blob(url: str, ref: Reference, token: list[str | None]) -> dict:
    """A config blob. Registries answer with a redirect to storage, which is followed once to a public host."""
    response = _get(url, ref, "application/json", token)
    if response.status_code in (301, 302, 307, 308) and response.headers.get("Location"):
        response = net.get(response.headers["Location"], timeout=TIMEOUT, allow_redirects=False)
    if response.status_code != 200:
        raise ImageError(f"The registry answered {response.status_code} for the image config")
    return response.json()


def _fetch(ref: Reference) -> ImageInfo:
    base = f"https://{ref.registry}/v2/{ref.repository}"
    token: list[str | None] = [None]
    response = _get(f"{base}/manifests/{ref.digest or ref.tag}", ref, MANIFEST_TYPES, token)
    if response.status_code in (401, 403, 404):
        raise ImageError(f"{ref.repository}:{ref.tag} was not found, or the image is private. Make it public.")
    if response.status_code != 200:
        raise ImageError(f"The registry answered {response.status_code} for {ref.repository}")
    digest = response.headers.get("Docker-Content-Digest") or ref.digest
    manifest = response.json()
    if manifest.get("mediaType") in INDEX_TYPES or "manifests" in manifest:
        entry = next(
            (
                m
                for m in manifest.get("manifests", [])
                if (m.get("platform") or {}).get("os") == "linux"
                and (m.get("platform") or {}).get("architecture") == "amd64"
            ),
            None,
        )
        if entry is None:
            raise ImageError(f"{ref.repository} has no linux/amd64 image")
        response = _get(f"{base}/manifests/{entry['digest']}", ref, MANIFEST_TYPES, token)
        if response.status_code != 200:
            raise ImageError(f"The registry answered {response.status_code} for the linux/amd64 image")
        manifest = response.json()
    config_digest = (manifest.get("config") or {}).get("digest")
    if not digest or not config_digest:
        raise ImageError(f"The registry gave no digest for {ref.repository}")
    labels = (_blob(f"{base}/blobs/{config_digest}", ref, token).get("config") or {}).get("Labels") or {}
    return ImageInfo(ref.pinned(digest), digest, labels.get(VERSION_LABEL))


def resolve(reference: str) -> ImageInfo:
    """The digest and godfather-base version of an image. Raises ImageError. Results are cached for 10 minutes."""
    ref = parse(reference.strip())

    def fetch() -> ImageInfo:
        try:
            return _fetch(ref)
        except ImageError:
            raise
        except (requests.RequestException, ValueError) as e:
            raise ImageError(f"Could not read {ref.repository} from {ref.registry}") from e

    return cache.get_or_compute(("godfather.image", reference.strip()), CACHE_SECONDS, fetch)


def check(info: ImageInfo, minimum: str) -> None:
    """Raise ImageError unless the image is godfather-base at or above minimum."""
    if not minimum:
        return
    if info.version is None:
        raise ImageError(f"The image has no {VERSION_LABEL} label. Build it FROM godfather-base {minimum} or later.")
    if not is_current(info.version, minimum):
        raise ImageError(f"The image is godfather-base {info.version}. Godfather needs {minimum} or later.")
