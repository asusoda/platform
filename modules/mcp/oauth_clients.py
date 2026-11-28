"""MCP OAuth clients: self-registered clients (RFC 7591) and Client ID Metadata Documents with their cache."""

import datetime
import json
from typing import cast
from urllib.parse import urlparse, urlsplit

from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl, ValidationError
from sqlalchemy.exc import IntegrityError

from core import secrets as org_secrets
from core.log import get_logger
from core.time import utcnow
from modules.auth.scopes import SCOPES
from modules.mcp import client_auth
from modules.mcp.models import OAuthClient
from modules.mcp.oauth import KEY_CLIENT, LOOPBACK_HOSTS, PUBLIC_CLIENT, OAuthError
from modules.mcp.oauth_fetch import Fetched, cache_time, fetch_public

# Self-registered clients and cached metadata documents have separate caps, so one kind cannot fill the other
MAX_REGISTERED_CLIENTS = 5000
MAX_DOCUMENT_CLIENTS = 5000
MAX_CLIENT_BYTES = 8192
# Client ID Metadata Documents: the limits of the URL and the fetch
METADATA_MAX_URL = 2048
METADATA_MAX_BYTES = 5 * 1024
# The document properties that Platform keeps. Others are ignored
METADATA_KEPT = (
    "client_name",
    "client_uri",
    "logo_uri",
    "redirect_uris",
    "grant_types",
    "response_types",
    "scope",
    "contacts",
    "tos_uri",
    "policy_uri",
    "software_id",
    "software_version",
    "jwks",
    "jwks_uri",
    "token_endpoint_auth_signing_alg",
)

logger = get_logger(__name__)


def check_redirect_uri(uri: str) -> None:
    """Refuse a redirect URI that the MCP spec does not allow: it must use https, or be on localhost."""
    parsed = urlparse(uri)
    scheme, host = parsed.scheme.lower(), parsed.hostname or ""
    if scheme == "http" and host in LOOPBACK_HOSTS:
        pass
    elif scheme != "https" or not host:
        raise OAuthError(f"Redirect URI {uri} must use https, or http on localhost")
    if parsed.fragment:
        raise OAuthError(f"Redirect URI {uri} must not have a fragment")


def same_loopback_uri(registered: str, requested: str) -> bool:
    """True when both URIs are http on the same loopback host and differ at most in the port (RFC 8252 7.3)."""
    a, b = urlsplit(registered), urlsplit(requested)
    if a.scheme.lower() != "http" or (a.hostname or "") not in LOOPBACK_HOSTS:
        return False
    parts = ("scheme", "hostname", "username", "password", "path", "query", "fragment")
    return all(getattr(a, part) == getattr(b, part) for part in parts)


class Client(OAuthClientInformationFull):
    """The SDK's client information, with any port allowed on a loopback redirect URI."""

    def validate_redirect_uri(self, redirect_uri: AnyUrl | None) -> AnyUrl:
        if redirect_uri is not None and any(
            same_loopback_uri(str(uri), str(redirect_uri)) for uri in self.redirect_uris or []
        ):
            return redirect_uri
        return super().validate_redirect_uri(redirect_uri)


def register_client(db, info: dict) -> None:
    """Store a client from the SDK's registration handler. Raises OAuthError. Commits."""
    secret = info.pop("client_secret", None)
    for uri in info.get("redirect_uris") or []:
        check_redirect_uri(str(uri))
    if len(json.dumps(info, default=str)) > MAX_CLIENT_BYTES:
        raise OAuthError(f"The client metadata is larger than {MAX_CLIENT_BYTES} bytes")
    if db.query(OAuthClient).filter(OAuthClient.cache_until.is_(None)).count() >= MAX_REGISTERED_CLIENTS:
        raise OAuthError(f"This server has {MAX_REGISTERED_CLIENTS} registered clients and cannot register more now")
    ciphertext = None
    if secret:
        ciphertext = org_secrets.encrypt(secret)
        if ciphertext is None:
            raise OAuthError('This server has no SECRETS_KEY. Register with token_endpoint_auth_method "none"')
    db.add(OAuthClient(client_id=info["client_id"], info=info, secret_ciphertext=ciphertext))
    db.commit()


# Client ID Metadata Documents


def is_metadata_url(client_id: str) -> bool:
    """Whether a client_id is the URL of a Client ID Metadata Document, not an id from /register."""
    return client_id.startswith("https://")


def check_metadata_url(url: str, name: str = "client_id") -> None:
    """Refuse a client_id (or jwks_uri) URL that the draft does not allow. Raises OAuthError."""
    parts = urlsplit(url)
    if len(url) > METADATA_MAX_URL:
        raise OAuthError(f"The {name} URL is longer than {METADATA_MAX_URL} characters")
    if parts.scheme != "https" or not parts.hostname:
        raise OAuthError(f"The {name} URL must use https")
    if parts.username is not None or parts.password is not None:
        raise OAuthError(f"The {name} URL must not have a user name or password")
    if parts.fragment or "#" in url:
        raise OAuthError(f"The {name} URL must not have a fragment")
    if len(parts.path) < 2:
        raise OAuthError(f"The {name} URL must have a path, such as /client.json")
    if {".", ".."} & set(parts.path.split("/")):
        raise OAuthError(f"The {name} URL must not have . or .. segments")


def fetch_metadata_document(url: str) -> Fetched:
    """GET a Client ID Metadata Document. Raises OAuthError. See oauth_fetch.fetch_public."""
    return fetch_public(url, METADATA_MAX_BYTES)


def client_from_document(url: str, fetched: Fetched) -> dict:
    """The client metadata from a fetched document, after the checks of the draft and the MCP spec. Raises OAuthError."""
    if fetched.status != 200:
        raise OAuthError(f"The client metadata document returned {fetched.status}, not 200")
    if len(fetched.body) > METADATA_MAX_BYTES:
        raise OAuthError(f"The client metadata document is larger than {METADATA_MAX_BYTES} bytes")
    try:
        document = json.loads(fetched.body)
    except ValueError as e:
        raise OAuthError("The client metadata document is not JSON") from e
    if not isinstance(document, dict):
        raise OAuthError("The client metadata document must be a JSON object")
    if document.get("client_id") != url:
        raise OAuthError("The client_id in the document must be the URL of the document")
    for name in ("client_name", "redirect_uris"):
        if not document.get(name):
            raise OAuthError(f"The client metadata document must have {name}")
    if "client_secret" in document or "client_secret_expires_at" in document:
        raise OAuthError("The client metadata document must not have a client secret")
    method = document.get("token_endpoint_auth_method", PUBLIC_CLIENT)
    if method not in (PUBLIC_CLIENT, KEY_CLIENT):
        raise OAuthError(
            f'token_endpoint_auth_method "{method}" is not supported. Use "{PUBLIC_CLIENT}" or "{KEY_CLIENT}"'
        )
    if method == KEY_CLIENT:
        check_client_keys(document)
    uris = document["redirect_uris"]
    if not isinstance(uris, list) or not all(isinstance(u, str) for u in uris):
        raise OAuthError("redirect_uris must be a list of URLs")
    for uri in uris:
        check_redirect_uri(uri)
    info = {key: document[key] for key in METADATA_KEPT if key in document}
    grants = info.setdefault("grant_types", ["authorization_code", "refresh_token"])
    if not isinstance(grants, list) or "authorization_code" not in grants:
        raise OAuthError("grant_types must have authorization_code")
    responses = info.setdefault("response_types", ["code"])
    if not isinstance(responses, list) or "code" not in responses:
        raise OAuthError("response_types must have code")
    # Platform scopes are granted on the consent page, so a client can ask for any of them
    asked = set(str(info.get("scope") or "").split())
    info |= {
        "client_id": url,
        "token_endpoint_auth_method": method,
        "scope": " ".join(sorted(asked | set(SCOPES))),
    }
    try:
        return OAuthClientInformationFull.model_validate(info).model_dump(mode="json", exclude_none=True)
    except ValidationError as e:
        raise OAuthError(f"The client metadata document is not valid: {e.errors()[0]['msg']}") from e


def check_client_keys(document: dict) -> None:
    """The public keys of a private_key_jwt client: jwks or an https jwks_uri, not both. Raises OAuthError."""
    jwks, jwks_uri = document.get("jwks"), document.get("jwks_uri")
    if (jwks is None) == (jwks_uri is None):
        raise OAuthError("A private_key_jwt client must have one of jwks and jwks_uri")
    if jwks_uri is not None:
        if not isinstance(jwks_uri, str):
            raise OAuthError("jwks_uri must be an https URL")
        check_metadata_url(jwks_uri, "jwks_uri")
    else:
        client_auth.parse_keys(jwks)


def resolve_client(db, client_id: str) -> dict | None:
    """The metadata of a client: a registered one, or the document at a client_id URL. Commits a fetched document.

    A cached document is used until its cache time ends. A document that cannot be fetched or is not valid
    gives None, and is not cached.
    """
    if not is_metadata_url(client_id):
        return get_client(db, client_id)
    now = utcnow()
    row = db.query(OAuthClient).filter_by(client_id=client_id).first()
    if row is not None and row.cache_until is not None and cast(datetime.datetime, row.cache_until) > now:
        return dict(cast(dict, row.info))
    try:
        check_metadata_url(client_id)
        fetched = fetch_metadata_document(client_id)
        info = client_from_document(client_id, fetched)
    except OAuthError as e:
        logger.warning("client metadata document refused client_id=%s: %s", client_id, e)
        return None
    until = now + cache_time(fetched.headers)
    if row is None:
        if db.query(OAuthClient).filter(OAuthClient.cache_until.isnot(None)).count() >= MAX_DOCUMENT_CLIENTS:
            logger.warning("client metadata document refused client_id=%s: too many clients", client_id)
            return None
        db.add(OAuthClient(client_id=client_id, info=info, cache_until=until))
    else:
        row.info = info
        row.cache_until = until
    try:
        db.commit()
    except IntegrityError:
        # Another request stored the same document first
        db.rollback()
    return info


def client_host(client_id: str) -> str | None:
    """The host name of a client_id URL, which the consent page shows. None for a registered client."""
    return urlsplit(client_id).hostname if is_metadata_url(client_id) else None


def get_client(db, client_id: str) -> dict | None:
    """The stored metadata of a client with its secret, or None. A document client gets its last cached document."""
    row = db.query(OAuthClient).filter_by(client_id=client_id).first()
    if row is None:
        return None
    info = dict(row.info)
    if row.secret_ciphertext is not None:
        secret = org_secrets.decrypt(str(row.secret_ciphertext))
        if secret is None:
            return None
        info["client_secret"] = secret
    return info


def touch(db, client_id: str) -> None:
    """Set the last use of a client. Does not commit."""
    db.query(OAuthClient).filter_by(client_id=client_id).update({"last_used_at": utcnow()})


def client_name(info: dict) -> str:
    return str(info.get("client_name") or "MCP client").strip()[:120] or "MCP client"
