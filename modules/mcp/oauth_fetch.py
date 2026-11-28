"""The fetch of an https URL that an OAuth client gives, such as its metadata document or jwks_uri."""

import datetime
import http.client
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlsplit

from core import net
from modules.mcp.oauth import OAuthError

TIMEOUT_SECONDS = 5
DEFAULT_CACHE = datetime.timedelta(hours=1)
MAX_CACHE = datetime.timedelta(hours=24)
USER_AGENT = "Platform MCP OAuth (+https://platform.thesoda.io)"


@dataclass(frozen=True)
class Fetched:
    status: int
    headers: dict[str, str]
    body: bytes


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS to an address that was checked before. The certificate must still match the host name."""

    def __init__(self, host: str, port: int, address: str, timeout: float):
        self._tls = ssl.create_default_context()
        super().__init__(host, port, timeout=timeout, context=self._tls)
        self._address = address

    def connect(self) -> None:
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._tls.wrap_socket(sock, server_hostname=self.host)


def fetch_public(url: str, limit: int) -> Fetched:
    """GET an https URL that a client gave. Raises OAuthError.

    The host must resolve only to public addresses, and the connection goes to one of those addresses. Platform
    does not follow redirects and reads at most limit and one byte more.
    """
    parts = urlsplit(url)
    host, port = str(parts.hostname), parts.port or 443
    try:
        address = net.public_addresses(host, port)[0]
    except (net.NoHost, net.NotPublic) as e:
        raise OAuthError(str(e)) from e
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    connection = _PinnedHTTPSConnection(host, port, address, TIMEOUT_SECONDS)
    try:
        connection.request("GET", target, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        response = connection.getresponse()
        body = response.read(limit + 1)
        return Fetched(response.status, {k.lower(): v for k, v in response.getheaders()}, body)
    except (OSError, http.client.HTTPException) as e:
        raise OAuthError(f"{url} could not be fetched: {type(e).__name__}") from e
    finally:
        connection.close()


def cache_time(headers: dict[str, str]) -> datetime.timedelta:
    """How long to keep a fetched document: its Cache-Control max-age, from 0 to MAX_CACHE."""
    directives = [d.strip().lower() for d in headers.get("cache-control", "").split(",") if d.strip()]
    if "no-store" in directives or "no-cache" in directives:
        return datetime.timedelta(0)
    for directive in directives:
        name, _, value = directive.partition("=")
        if name == "max-age" and value.strip().isdigit():
            return min(datetime.timedelta(seconds=int(value.strip())), MAX_CACHE)
    return DEFAULT_CACHE
