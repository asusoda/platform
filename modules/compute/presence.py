"""Live SSH sessions on a pod, read over the root backend connection. No Flask here.

The pod image contract runs /usr/local/bin/godfather-login for each CLI connection. A member session
runs as su - godfather_<username>. An officer session runs bash with /etc/godfather/admin.bashrc
and GODFATHER_USER=<username> in its environment. A pod without godfather-login gives no answer.
"""

import re
from typing import Any

import paramiko

from core.errors import ServiceError
from core.log import get_logger

from . import files

logger = get_logger("compute.presence")

TIMEOUT_SECONDS = 5
NO_CONTRACT_STATUS = 3
# A fixed script with no outside input. Each output line is: kind seconds username-field.
SCRIPT = (
    f"test -x /usr/local/bin/godfather-login || exit {NO_CONTRACT_STATUS}; "
    "ps -eo pid=,etimes=,args= | while read -r pid secs args; do "
    'case "$args" in '
    '"su - godfather_"*) echo "member $secs ${args#su - godfather_}" ;; '
    '"bash --rcfile /etc/godfather/admin.bashrc"*) '
    "echo \"admin $secs $(grep -az '^GODFATHER_USER=' /proc/$pid/environ 2>/dev/null | tr -d '\\0')\" ;; "
    "esac; done"
)
USERNAME_RE = re.compile(r"^[a-z0-9_][a-z0-9._-]{0,21}$")
MAX_OUTPUT_BYTES = 200_000


class PresenceUnknown(ServiceError):
    """The live sessions of a pod cannot be read."""


def parse(output: str) -> list[dict]:
    """Sessions from the script output: username, is_admin and seconds, longest first."""
    sessions = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0] not in ("member", "admin") or not parts[1].isdigit():
            continue
        name = parts[2].removeprefix("GODFATHER_USER=") if parts[0] == "admin" else parts[2]
        if not USERNAME_RE.match(name):
            continue
        sessions.append({"username": name, "is_admin": parts[0] == "admin", "seconds": int(parts[1])})
    return sorted(sessions, key=lambda s: (-s["seconds"], s["username"]))


def run(client: Any) -> list[dict]:
    """The live sessions on a pod, from an open SSH client. Raises PresenceUnknown."""
    try:
        # SCRIPT is a constant with no outside input
        _, stdout, _ = client.exec_command(SCRIPT, timeout=TIMEOUT_SECONDS)  # nosec B601
        output = stdout.read(MAX_OUTPUT_BYTES)
        status = stdout.channel.recv_exit_status()
    except (paramiko.SSHException, OSError) as e:
        raise PresenceUnknown("The command on the pod failed", 502) from e
    if status == NO_CONTRACT_STATUS:
        raise PresenceUnknown("The pod image has no godfather-login, so its sessions cannot be read", 409)
    if status != 0:
        raise PresenceUnknown("The command on the pod failed", 502)
    return parse(output.decode("utf-8", "replace"))


def sessions(host: str, port: int, private_key: str, opener=None) -> list[dict]:
    """The live sessions on a pod at host and port. Raises PresenceUnknown."""
    try:
        client = (opener or files.open_ssh)(host, port, private_key, TIMEOUT_SECONDS)
    except files.FilesError as e:
        raise PresenceUnknown(e.message, e.status) from e
    try:
        return run(client)
    finally:
        client.close()
