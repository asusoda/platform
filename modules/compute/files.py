"""Files on a pod over SFTP, as root with the org's backend key. No Flask here.

Every path is absolute and normalized before use. Shell commands quote every argument.
"""

import io
import posixpath
import shlex
import stat
from collections.abc import Callable
from typing import Any, cast

import paramiko

from core.errors import ServiceError
from core.log import get_logger

logger = get_logger("compute.files")

MAX_READ_BYTES = 1_000_000
MAX_TRANSFER_BYTES = 100_000_000
CONNECT_TIMEOUT_SECONDS = 10
COMMAND_TIMEOUT_SECONDS = 60


class FilesError(ServiceError):
    """A file operation on a pod failed or was refused."""


def clean_path(path: object) -> str:
    """An absolute, normalized POSIX path, or FilesError."""
    if not isinstance(path, str) or not path.startswith("/") or "\x00" in path or len(path) > 4096:
        raise FilesError("path must be an absolute path")
    cleaned = posixpath.normpath(path)
    return "/" if cleaned in ("/", "//") else cleaned


def _load_key(private_key: str) -> paramiko.PKey:
    for key_class in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return key_class.from_private_key(io.StringIO(private_key))
        except paramiko.SSHException:
            continue
    raise FilesError("The backend key cannot be read", 500)


class PodFiles:
    """An open SFTP session on one pod. Use as a context manager."""

    def __init__(self, client: Any, sftp: Any):
        self._client = client
        self._sftp = sftp

    @classmethod
    def open(cls, host: str, port: int, private_key: str) -> "PodFiles":
        client = paramiko.SSHClient()
        # Pods are created and replaced often and publish no host keys to check against
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507
        try:
            client.connect(
                hostname=host,
                port=port,
                username="root",
                pkey=_load_key(private_key),
                timeout=CONNECT_TIMEOUT_SECONDS,
                look_for_keys=False,
                allow_agent=False,
            )
            return cls(client, client.open_sftp())
        except (paramiko.SSHException, OSError) as e:
            client.close()
            logger.warning("SSH to %s:%s failed: %s", host, port, e)
            raise FilesError("Could not connect to the pod", 502) from e

    def __enter__(self) -> "PodFiles":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        for handle in (self._sftp, self._client):
            try:
                handle.close()
            except Exception:  # noqa: BLE001
                logger.debug("close failed", exc_info=True)

    def _sftp_call(self, fn: Callable, *args) -> Any:
        try:
            return fn(*args)
        except FileNotFoundError as e:
            raise FilesError("No such file or directory", 404) from e
        except PermissionError as e:
            raise FilesError("Permission denied", 403) from e
        except (OSError, paramiko.SSHException) as e:
            raise FilesError(f"The pod refused: {e}", 409) from e

    def _remove(self, target: str) -> None:
        command = f"rm -rf -- {shlex.quote(target)}"
        try:
            # The only argument is quoted with shlex
            _, stdout, stderr = self._client.exec_command(command, timeout=COMMAND_TIMEOUT_SECONDS)  # nosec B601
            status = stdout.channel.recv_exit_status()
        except (paramiko.SSHException, OSError) as e:
            raise FilesError("The command on the pod failed", 502) from e
        if status != 0:
            raise FilesError(stderr.read().decode("utf-8", "replace").strip()[:300] or "The command failed", 409)

    def list(self, path: object) -> list[dict]:
        """Entries of a directory, directories first."""
        entries = self._sftp_call(self._sftp.listdir_attr, clean_path(path))
        items = [
            {
                "name": e.filename,
                "type": "directory" if stat.S_ISDIR(e.st_mode or 0) else "file",
                "size": e.st_size or 0,
                "modified": e.st_mtime or 0,
                "permissions": oct(e.st_mode or 0)[-3:],
            }
            for e in entries
        ]
        return sorted(items, key=lambda item: (item["type"] == "file", item["name"]))

    def _size(self, path: str) -> int:
        return int(self._sftp_call(self._sftp.stat, path).st_size or 0)

    def read_text(self, path: object) -> str:
        """A text file, up to MAX_READ_BYTES."""
        target = clean_path(path)
        if self._size(target) > MAX_READ_BYTES:
            raise FilesError(f"The file is larger than {MAX_READ_BYTES} bytes; download it instead", 413)
        with self._sftp_call(self._sftp.open, target, "r") as handle:
            return cast(bytes, handle.read()).decode("utf-8", errors="replace")

    def write_text(self, path: object, content: object) -> None:
        if not isinstance(content, str) or len(content.encode()) > MAX_READ_BYTES:
            raise FilesError(f"content must be text of at most {MAX_READ_BYTES} bytes")
        with self._sftp_call(self._sftp.open, clean_path(path), "w") as handle:
            handle.write(content.encode("utf-8"))

    def download(self, path: object) -> bytes:
        target = clean_path(path)
        if self._size(target) > MAX_TRANSFER_BYTES:
            raise FilesError(f"The file is larger than {MAX_TRANSFER_BYTES} bytes", 413)
        buffer = io.BytesIO()
        self._sftp_call(self._sftp.getfo, target, buffer)
        return buffer.getvalue()

    def upload(self, directory: object, filename: object, stream: Any) -> str:
        """Store an uploaded file in a directory. Returns its path."""
        if not isinstance(filename, str) or not filename or "/" in filename or filename in (".", ".."):
            raise FilesError("The file needs a plain name")
        target = posixpath.join(clean_path(directory), filename)
        self._sftp_call(self._sftp.putfo, stream, target)
        return target

    def mkdir(self, path: object) -> None:
        self._sftp_call(self._sftp.mkdir, clean_path(path))

    def rename(self, old: object, new: object) -> None:
        self._sftp_call(self._sftp.rename, clean_path(old), clean_path(new))

    def delete(self, path: object) -> None:
        """Delete a file, or a directory with everything in it."""
        target = clean_path(path)
        if target in ("/", "/workspace", "/root", "/home"):
            raise FilesError("That directory cannot be deleted")
        self._remove(target)
