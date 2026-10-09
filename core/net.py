"""Checks that a URL names a public host, so a URL from a user cannot make the server reach its own network."""

import ipaddress
import socket
from urllib.parse import urlsplit


class NotPublic(ValueError):
    """The URL is not http(s), or its host resolves to a non-public address."""


class NoHost(ValueError):
    """The host of the URL does not resolve."""


def check_public(url: str) -> None:
    """Raise NotPublic unless url is http(s) on a host that resolves only to public addresses."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise NotPublic(f"Only http and https URLs are allowed: {url}")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as e:
        raise NoHost(f"{parts.hostname} does not resolve") from e
    for info in infos:
        address = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if not address.is_global:
            raise NotPublic(f"{parts.hostname} resolves to a non-public address")
