"""The OAuth discovery documents of the MCP server (RFC 9728, RFC 8414) and the SDK's registration options."""

from mcp.server.auth.routes import build_metadata
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import ProtectedResourceMetadata
from pydantic import AnyHttpUrl

from modules.auth.scopes import SCOPES
from modules.mcp import client_auth
from modules.mcp.oauth import KEY_CLIENT, PUBLIC_CLIENT, public_path, public_url

# The scopes that a new connection asks for (scope hint): enough to read the org. A tool that needs more
# asks for its scope with step-up (edges.py)
BASE_SCOPES = ("org:read",)
REGISTRATION = ClientRegistrationOptions(enabled=True)
REVOCATION = RevocationOptions(enabled=True)


def resource_metadata_path() -> str:
    """Where a client reads the protected resource metadata (RFC 9728), at the root of the host."""
    return f"/.well-known/oauth-protected-resource{public_path()}"


def server_metadata_paths() -> list[str]:
    """Where clients read the authorization server metadata (RFC 8414), at the root of the host.

    A client that follows the MCP spec inserts the issuer's path: /.well-known/oauth-authorization-server/mcp.
    Some clients, such as Composio, only read /.well-known/oauth-authorization-server and also need the issuer
    to be the public URL, so the same document is there too.
    """
    return [f"/.well-known/oauth-authorization-server{public_path()}", "/.well-known/oauth-authorization-server"]


def resource_metadata() -> dict:
    """The protected resource metadata (RFC 9728). scopes_supported is the minimal set for a new connection."""
    url = AnyHttpUrl(public_url())
    metadata = ProtectedResourceMetadata(
        resource=url, authorization_servers=[url], scopes_supported=list(BASE_SCOPES), resource_name="Platform"
    )
    return metadata.model_dump(mode="json", exclude_none=True)


def server_metadata_model():
    """The authorization server metadata (RFC 8414). It adds Client ID Metadata Documents, RFC 9207 iss and
    private_key_jwt."""
    metadata = build_metadata(AnyHttpUrl(public_url()), None, REGISTRATION, REVOCATION)
    metadata.client_id_metadata_document_supported = True
    metadata.authorization_response_iss_parameter_supported = True
    metadata.scopes_supported = sorted(SCOPES)
    methods = ["client_secret_post", "client_secret_basic", KEY_CLIENT, PUBLIC_CLIENT]
    metadata.token_endpoint_auth_methods_supported = methods
    metadata.revocation_endpoint_auth_methods_supported = methods
    metadata.token_endpoint_auth_signing_alg_values_supported = list(client_auth.ALGORITHMS)
    metadata.revocation_endpoint_auth_signing_alg_values_supported = list(client_auth.ALGORITHMS)
    return metadata


def server_metadata() -> dict:
    return server_metadata_model().model_dump(mode="json", exclude_none=True)
