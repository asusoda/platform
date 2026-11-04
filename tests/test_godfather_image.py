"""The godfather-base image check: reference parsing, version compare and the registry handshake."""

import json

import pytest

from modules.godfather import image


def test_parse_references():
    ghcr = image.parse("ghcr.io/theaisocietyasu/godfather-base:2.3.0")
    assert (ghcr.registry, ghcr.repository, ghcr.tag) == ("ghcr.io", "theaisocietyasu/godfather-base", "2.3.0")
    hub = image.parse("ubuntu")
    assert (hub.registry, hub.repository, hub.tag) == ("registry-1.docker.io", "library/ubuntu", "latest")
    assert hub.pinned("sha256:abc") == "library/ubuntu@sha256:abc"
    local = image.parse("localhost:5000/team/pod@sha256:" + "a" * 64)
    assert (local.registry, local.repository, local.digest) == ("localhost:5000", "team/pod", "sha256:" + "a" * 64)
    assert ghcr.pinned("sha256:abc") == "ghcr.io/theaisocietyasu/godfather-base@sha256:abc"
    with pytest.raises(image.ImageError):
        image.parse("Not An Image")


def test_version_compare():
    assert image.is_current("2.3.0", "2.2.0") and image.is_current("2.10.0", "2.9.1")
    assert not image.is_current("2.1.9", "2.2.0")
    assert not image.is_current(None, "2.2.0") and not image.is_current("dev", "2.2.0")
    assert image.is_current(None, "")


class Answer:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body or {}

    def json(self):
        return json.loads(json.dumps(self._body))


def test_resolve_reads_the_amd64_config_labels_with_an_anonymous_token(monkeypatch):
    from core.cache import cache

    cache.invalidate("godfather.image")
    base = "https://ghcr.io/v2/theaisocietyasu/godfather-base"
    calls = []

    def get(url, headers=None, params=None, **kwargs):
        calls.append(url)
        authorized = (headers or {}).get("Authorization") == "Bearer t0k"
        if url == "https://pkg-containers.example/blob":
            assert not headers
            return Answer(200, {"config": {"Labels": {image.VERSION_LABEL: "2.3.0"}}})
        if url == "https://ghcr.io/token":
            assert (params or {}).get("scope") == "repository:theaisocietyasu/godfather-base:pull"
            return Answer(200, {"token": "t0k"})
        if not authorized:
            return Answer(401, headers={"WWW-Authenticate": 'Bearer realm="https://ghcr.io/token",service="ghcr.io"'})
        if url == f"{base}/manifests/2.3.0":
            index = {
                "mediaType": "application/vnd.oci.image.index.v1+json",
                "manifests": [
                    {"digest": "sha256:arm", "platform": {"os": "linux", "architecture": "arm64"}},
                    {"digest": "sha256:amd", "platform": {"os": "linux", "architecture": "amd64"}},
                ],
            }
            return Answer(200, index, {"Docker-Content-Digest": "sha256:index"})
        if url == f"{base}/manifests/sha256:amd":
            return Answer(200, {"config": {"digest": "sha256:cfg"}})
        if url == f"{base}/blobs/sha256:cfg":
            return Answer(307, headers={"Location": "https://pkg-containers.example/blob"})
        raise AssertionError(url)

    monkeypatch.setattr(image.net, "get", get)
    info = image.resolve("ghcr.io/theaisocietyasu/godfather-base:2.3.0")
    assert info == image.ImageInfo("ghcr.io/theaisocietyasu/godfather-base@sha256:index", "sha256:index", "2.3.0")
    image.check(info, "2.2.0")
    with pytest.raises(image.ImageError):
        image.check(info, "2.4.0")
    with pytest.raises(image.ImageError):
        image.check(image.ImageInfo("x", "sha256:x", None), "2.2.0")
    cache.invalidate("godfather.image")


def test_a_private_or_missing_image_is_refused(monkeypatch):
    from core.cache import cache

    cache.invalidate("godfather.image")
    monkeypatch.setattr(image.net, "get", lambda url, **kwargs: Answer(404))
    with pytest.raises(image.ImageError) as e:
        image.resolve("ghcr.io/example/private:1")
    assert "private" in e.value.message and e.value.status == 422
