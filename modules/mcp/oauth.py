"""OAuth 2.1 for the MCP server: the public URL, the error type and the helpers that each OAuth file uses.

Every OAuth URL is under the public URL of /mcp (public_url), so one reverse proxy location reaches them all.
The mcp SDK serves <url>/register, /authorize, /token and /revoke and checks the protocol. Platform stores
clients, requests and grants and is the SDK's provider. No Flask in any of these files:

- oauth.py: the public URL, OAuthError and shared helpers
- oauth_discovery.py: the discovery documents (RFC 9728, RFC 8414) and the SDK's registration options
- oauth_rate_limit.py: the limit of requests of each client IP
- oauth_fetch.py: the fetch of a URL that a client gives (metadata documents, jwks_uri)
- oauth_clients.py: registered clients and Client ID Metadata Documents
- oauth_requests.py: authorization requests, the officer check and authorization codes
- oauth_grants.py: the code exchange, refresh, revocation and cleanup of grants
- oauth_provider.py: the provider of the mcp SDK
- oauth_pages.py: the sign-in and consent pages
- client_auth.py: private_key_jwt client authentication

A client registers itself (RFC 7591), or uses the HTTPS URL of its Client ID Metadata Document as its
client_id (draft-ietf-oauth-client-id-metadata-document). Platform then fetches that document, checks it and
keeps it in oauth_clients for the time that its cache headers allow.

The access token is a machine token of kind oauth, so the MCP server, scopes, limits and the Connections page
treat it as any other machine token. An officer approves the org, the scopes and the integration limits.
A refresh gives the same machine token row a new value, after a check that the officer still has the
officer role. When an officer revokes that token, the refresh token stops working too.
"""

import datetime
import hashlib
from typing import cast
from urllib.parse import urlparse, urlsplit

from core import sign_in
from core.config import config

LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "[::1]", "::1")
# The client authentication of a document client: none (a public client with PKCE), or a signed assertion
# with a key from its jwks or jwks_uri (RFC 7523, client_auth.py)
PUBLIC_CLIENT = "none"
KEY_CLIENT = "private_key_jwt"


class OAuthError(ValueError):
    pass


# The message of the OAuthError for a refresh that asks for a scope outside the grant
INVALID_SCOPE = "invalid_scope"


def hash_value(value: str) -> str:
    """The SHA-256 hex digest that the OAuth tables store in place of a key, code or refresh token."""
    return hashlib.sha256(value.encode()).hexdigest()


def epoch(moment: object) -> int:
    """Seconds since 1970 for a naive UTC datetime column."""
    return int(cast(datetime.datetime, moment).replace(tzinfo=datetime.UTC).timestamp())


def strings(value: object) -> list[str]:
    """A JSON list column as a list of strings."""
    return [str(v) for v in cast(list, value or [])]


def optional_text(value: object) -> str | None:
    return None if value is None else str(value)


# The public URL


def url_problem(url: str) -> str | None:
    """Why OAuth cannot use this public URL of /mcp, or None when it can."""
    parsed = urlparse(url)
    if not parsed.hostname or parsed.query or parsed.fragment:
        return f"{url} must be a URL with no query or fragment"
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS):
        return f"{url} must use https, or http on localhost"
    return None


def configured_url() -> str:
    """MCP_PUBLIC_URL, else <ACCOUNTS_BASE_URL>/mcp, else "". A URL with no path gets /mcp."""
    url = config.MCP_PUBLIC_URL or (f"{sign_in.base_url()}/mcp" if sign_in.base_url() else "")
    if url and urlparse(url).path in ("", "/"):
        url = url.rstrip("/") + "/mcp"
    return url.rstrip("/")


def public_url() -> str:
    """The public URL of /mcp, such as https://api.example.org/mcp, or "" when OAuth is off."""
    url = configured_url()
    return url if url and url_problem(url) is None else ""


def public_path() -> str:
    """The path of the public URL, such as /mcp. The MCP server serves /mcp and OAuth under it."""
    return urlparse(public_url()).path or "/mcp"


def same_resource(resource: str) -> bool:
    """Whether an RFC 8707 resource names this MCP server: its public URL, or a path above it on the same origin."""
    ours, theirs = urlsplit(public_url()), urlsplit(resource.strip())
    if (theirs.scheme.lower(), (theirs.netloc or "").lower()) != (ours.scheme.lower(), ours.netloc.lower()):
        return False
    if theirs.query or theirs.fragment:
        return False
    path = theirs.path.rstrip("/")
    return ours.path.rstrip("/") == path or ours.path.startswith(path + "/")
