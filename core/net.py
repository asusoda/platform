"""Checks that a URL names a public host, so a URL from a user cannot make the server reach its own network.

get(), post() and request() connect only to an address that passed the check. A second DNS answer cannot move
the connection to a private address. An IPv6 address that holds an IPv4 address (IPv4-mapped, 6to4, NAT64) must
pass the check by its IPv4 part too.

Each call uses a new session, so no cookie from one call goes with the next. The connection pools are shared.
Proxies from the environment are not used (a proxy would resolve the host again), but REQUESTS_CA_BUNDLE and
CURL_CA_BUNDLE are.
"""

import ipaddress
import os
import socket
from typing import Any, ClassVar
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NameResolutionError, NewConnectionError
from urllib3.poolmanager import PoolManager
from urllib3.util.connection import _TYPE_SOCKET_OPTIONS, create_connection


class NotPublic(ValueError):
    """The URL is not http(s), or its host resolves to a non-public address."""


class NoHost(ValueError):
    """The host of the URL does not resolve."""


NAT64 = ipaddress.ip_network("64:ff9b::/96")


def _is_public(address: str) -> bool:
    """Whether the address is global, and also its embedded IPv4 address when it has one."""
    ip = ipaddress.ip_address(address)
    if not ip.is_global:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = ip.ipv4_mapped or ip.sixtofour
        if embedded is None and ip in NAT64:
            embedded = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if embedded is not None and not embedded.is_global:
            return False
    return True


def public_addresses(host: str, port: int) -> list[str]:
    """The addresses of host, after a check that each one is public. Raises NoHost or NotPublic.

    Connect to one of these, not to the host name: a second lookup can give another address.
    """
    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror as e:
        raise NoHost(f"{host} does not resolve") from e
    addresses = [str(info[4][0]).split("%")[0] for info in infos]
    for address in addresses:
        if not _is_public(address):
            raise NotPublic(f"{host} resolves to a non-public address")
    if not addresses:
        raise NoHost(f"{host} does not resolve")
    return addresses


def check_public(url: str) -> None:
    """Raise NotPublic unless url is http(s) on a host that resolves only to public addresses."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise NotPublic(f"Only http and https URLs are allowed: {url}")
    public_addresses(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))


def _connect_public(connection: HTTPConnection) -> socket.socket:
    """A socket to the first public address of the connection's host that accepts. TLS still uses the host name."""
    host, port = connection.host, connection.port
    try:
        addresses = public_addresses(host, port)
    except NoHost as e:
        raise NameResolutionError(host, connection, socket.gaierror(str(e))) from e
    error: OSError | None = None
    for address in dict.fromkeys(addresses):
        try:
            return create_connection(
                (address, port),
                connection.timeout,
                source_address=connection.source_address,
                socket_options=connection.socket_options,
            )
        except OSError as e:
            error = e
    if isinstance(error, TimeoutError):
        raise ConnectTimeoutError(
            connection, f"Connection to {host} timed out. (connect timeout={connection.timeout})"
        ) from error
    raise NewConnectionError(connection, f"Failed to establish a new connection: {error}")


class _PublicHTTPConnection(HTTPConnection):
    def _new_conn(self) -> socket.socket:
        return _connect_public(self)


class _PublicHTTPSConnection(HTTPSConnection):
    def _new_conn(self) -> socket.socket:
        return _connect_public(self)


class _PublicHTTPPool(HTTPConnectionPool):
    ConnectionCls = _PublicHTTPConnection

    default_socket_options: ClassVar[_TYPE_SOCKET_OPTIONS] = []


class _PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _PublicHTTPSConnection

    default_socket_options: ClassVar[_TYPE_SOCKET_OPTIONS] = []


class _PublicPoolManager(PoolManager):
    """A pool manager whose pools open connections with _connect_public."""

    pool_classes_by_scheme: dict[str, type[HTTPConnectionPool]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pool_classes_by_scheme = {"http": _PublicHTTPPool, "https": _PublicHTTPSPool}


class _PublicAdapter(HTTPAdapter):
    """An adapter whose connections check the host's addresses and connect to one that passed."""

    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any) -> None:
        super().init_poolmanager(connections, maxsize, block, **pool_kwargs)
        self.poolmanager = _PublicPoolManager(num_pools=connections, maxsize=maxsize, block=block, **pool_kwargs)


_HTTP = _PublicAdapter()
_HTTPS = _PublicAdapter()


def _session() -> requests.Session:
    """A new session with no cookies that reaches public addresses only, through the shared pools."""
    session = requests.Session()
    session.trust_env = False
    session.verify = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE") or True
    session.mount("http://", _HTTP)
    session.mount("https://", _HTTPS)
    return session


def request(method: str, url: str, **kwargs: Any) -> requests.Response:
    """requests.request to a public address only. Raises NotPublic or a requests.RequestException."""
    return _session().request(method, url, **kwargs)


def get(url: str, **kwargs: Any) -> requests.Response:
    """requests.get to a public address only. Raises NotPublic or a requests.RequestException."""
    return request("GET", url, **kwargs)


def post(url: str, **kwargs: Any) -> requests.Response:
    """requests.post to a public address only. Raises NotPublic or a requests.RequestException."""
    return request("POST", url, **kwargs)
