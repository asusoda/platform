"""The pod start script takes Sparky's binaries out of its image with deploy/runpod/image_files.py."""

import gzip
import io
import tarfile

from deploy.runpod.image_files import extract, parse


def layer(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o755
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buffer.getvalue())


def test_parse_names_the_registry_repository_and_tag():
    assert parse("ghcr.io/ashworks1706/sparkyai-rust:main") == ("ghcr.io", "ashworks1706/sparkyai-rust", "main")
    assert parse("ghcr.io/org/app") == ("ghcr.io", "org/app", "latest")
    assert parse("python:3.12") == ("registry-1.docker.io", "library/python", "3.12")
    assert parse("localhost.dev:5000/app") == ("localhost.dev:5000", "app", "latest")


def test_extract_writes_only_the_wanted_files(tmp_path):
    blob = layer({"engine": b"bin", "./sparky.toml": b"toml", "etc/passwd": b"x"})
    found = extract(blob, {"engine", "sparky.toml", "discord"}, tmp_path)
    assert found == {"engine", "sparky.toml"}
    assert (tmp_path / "engine").read_bytes() == b"bin"
    assert (tmp_path / "engine").stat().st_mode & 0o111
    assert not (tmp_path / "etc").exists()
