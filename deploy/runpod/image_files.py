"""Copies files out of a public container image without a container runtime.

RunPod pods cannot run containers, so the pod start script uses this to take prebuilt binaries
from an image. Usage from the repository root: python -m deploy.runpod.image_files IMAGE:TAG DEST FILE [FILE ...]

FILE is a path in the image without the leading slash. The files of the newest layer win. DEST keeps the
digest of the image it holds, so a start with an unchanged image downloads nothing.
"""

import gzip
import io
import re
import sys
import tarfile
from pathlib import Path

import requests

from core.log import get_logger

logger = get_logger(__name__)

TIMEOUT = 60
INDEX_TYPES = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


def parse(ref: str) -> tuple[str, str, str]:
    """Registry host, repository and tag of an image reference."""
    name, _, tag = ref.rpartition(":")
    if not name or "/" in tag:
        name, tag = ref, "latest"
    host, _, repo = name.partition("/")
    if "." not in host:
        host, repo = "registry-1.docker.io", name if "/" in name else f"library/{name}"
    return host, repo, tag


def token(session: requests.Session, host: str, repo: str) -> str | None:
    """Anonymous pull token, or None when the registry asks for none."""
    probe = session.get(f"https://{host}/v2/", timeout=TIMEOUT)
    challenge = probe.headers.get("WWW-Authenticate", "")
    if probe.status_code != 401 or not challenge.lower().startswith("bearer"):
        return None
    params = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
    realm = params.pop("realm")
    params["scope"] = f"repository:{repo}:pull"
    reply = session.get(realm, params=params, timeout=TIMEOUT)
    reply.raise_for_status()
    body = reply.json()
    return body.get("token") or body.get("access_token")


def manifest(session: requests.Session, base: str, tag: str) -> tuple[str, dict]:
    """Digest and manifest of the linux/amd64 image at tag."""
    reply = session.get(f"{base}/manifests/{tag}", headers={"Accept": INDEX_TYPES}, timeout=TIMEOUT)
    reply.raise_for_status()
    body = reply.json()
    if "manifests" not in body:
        return reply.headers.get("Docker-Content-Digest", tag), body
    for entry in body["manifests"]:
        platform = entry.get("platform", {})
        if platform.get("os") == "linux" and platform.get("architecture") == "amd64":
            return manifest(session, base, entry["digest"])
    raise SystemExit(f"no linux/amd64 image at {base}:{tag}")


def extract(blob: bytes, wanted: set[str], dest: Path) -> set[str]:
    """Writes the wanted files found in one gzip layer to dest and returns their names."""
    found = set()
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(blob))) as layer:
        for member in layer.getmembers():
            name = member.name.removeprefix("./").lstrip("/")
            if name not in wanted or not member.isfile():
                continue
            source = layer.extractfile(member)
            if source is None:
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read())
            target.chmod(member.mode & 0o755)
            found.add(name)
    return found


def main(ref: str, dest_dir: str, files: list[str]) -> None:
    host, repo, tag = parse(ref)
    dest = Path(dest_dir)
    session = requests.Session()
    pull_token = token(session, host, repo)
    if pull_token:
        session.headers["Authorization"] = f"Bearer {pull_token}"
    base = f"https://{host}/v2/{repo}"
    digest, image = manifest(session, base, tag)

    stamp = dest / ".digest"
    if stamp.is_file() and stamp.read_text().strip() == digest and all((dest / f).is_file() for f in files):
        logger.info("%s unchanged (%s)", ref, digest)
        return

    dest.mkdir(parents=True, exist_ok=True)
    wanted = set(files)
    for layer in reversed(image["layers"]):
        if not wanted:
            break
        if not layer["mediaType"].endswith("gzip"):
            raise SystemExit(f"layer type {layer['mediaType']} is not supported")
        reply = session.get(f"{base}/blobs/{layer['digest']}", timeout=TIMEOUT)
        reply.raise_for_status()
        wanted -= extract(reply.content, wanted, dest)
    if wanted:
        raise SystemExit(f"not in {ref}: {', '.join(sorted(wanted))}")
    stamp.write_text(digest)
    logger.info("%s copied to %s (%s)", ref, dest, digest)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
