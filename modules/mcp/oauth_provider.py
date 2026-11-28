"""The OAuthAuthorizationServerProvider of the mcp SDK, on top of the MCP OAuth tables."""

from anyio import to_thread
from mcp.server.auth import provider as sdk
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from core.db import db_connect
from modules.auth import machine_tokens
from modules.auth.scopes import SCOPES
from modules.mcp import oauth_clients, oauth_grants, oauth_requests
from modules.mcp.oauth import INVALID_SCOPE, OAuthError, epoch, optional_text, public_url, same_resource, strings


class PlatformAccessToken(sdk.AccessToken):
    token_id: int


class PlatformRefreshToken(sdk.RefreshToken):
    token_id: int


def _session(func, *args):
    db = db_connect.SessionLocal()
    try:
        return func(db, *args)
    finally:
        db.close()


async def _run(func, *args):
    return await to_thread.run_sync(_session, func, *args)


def _verify(db, token: str) -> PlatformAccessToken | None:
    caller = machine_tokens.verify(db, token)
    if caller is None:
        return None
    return PlatformAccessToken(
        token=token,
        client_id=oauth_grants.client_of_token(db, caller.token_id) or caller.actor,
        scopes=sorted(caller.scopes),
        subject=caller.created_by,
        token_id=caller.token_id,
    )


class Provider(sdk.OAuthAuthorizationServerProvider[sdk.AuthorizationCode, PlatformRefreshToken, PlatformAccessToken]):
    """The OAuthAuthorizationServerProvider of the mcp SDK. login_url gives the sign-in page of a request."""

    def __init__(self, login_url):
        self.login_url = login_url

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        info = await _run(oauth_clients.resolve_client, client_id)
        return oauth_clients.Client.model_validate(info) if info is not None else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        # Platform scopes are granted on the consent page, so a client can ask for any of them
        asked = set((client_info.scope or "").split())
        client_info.scope = " ".join(sorted(asked | set(SCOPES)))
        try:
            await _run(oauth_clients.register_client, client_info.model_dump(mode="json", exclude_none=True))
        except OAuthError as e:
            code = "invalid_redirect_uri" if "Redirect URI" in str(e) else "invalid_client_metadata"
            raise sdk.RegistrationError(code, str(e)) from e

    async def authorize(self, client: OAuthClientInformationFull, params: sdk.AuthorizationParams) -> str:
        if params.resource and not same_resource(params.resource):
            raise sdk.AuthorizeError("invalid_target", f"This server is {public_url()}, not {params.resource}")
        key = await _run(oauth_requests.start, str(client.client_id), params.model_dump(mode="json"))
        return self.login_url(key)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> sdk.AuthorizationCode | None:
        def load(db):
            row = oauth_requests.load_code(db, str(client.client_id), authorization_code)
            if row is None:
                return None
            return sdk.AuthorizationCode(
                code=authorization_code,
                scopes=strings(row.scopes),
                expires_at=float(epoch(row.expires_at)),
                client_id=str(row.client_id),
                code_challenge=str(row.code_challenge),
                redirect_uri=AnyUrl(str(row.redirect_uri)),
                redirect_uri_provided_explicitly=bool(row.redirect_uri_explicit),
                resource=optional_text(row.resource),
                subject=optional_text(row.discord_id),
            )

        return await _run(load)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: sdk.AuthorizationCode
    ) -> OAuthToken:
        try:
            token = await _run(oauth_grants.exchange_code, str(client.client_id), authorization_code.code)
        except OAuthError as e:
            raise sdk.TokenError("invalid_grant", str(e)) from e
        return OAuthToken.model_validate(token)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> PlatformRefreshToken | None:
        found = await _run(oauth_grants.load_refresh, str(client.client_id), refresh_token)
        if found is None:
            return None
        return PlatformRefreshToken(token=refresh_token, client_id=str(client.client_id), **found)

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: PlatformRefreshToken, scopes: list[str]
    ) -> OAuthToken:
        try:
            token = await _run(oauth_grants.exchange_refresh, str(client.client_id), refresh_token.token, scopes)
        except OAuthError as e:
            if str(e) == INVALID_SCOPE:
                raise sdk.TokenError("invalid_scope", "The refresh asks for a scope outside the grant") from e
            raise sdk.TokenError("invalid_grant", str(e)) from e
        return OAuthToken.model_validate(token)

    async def load_access_token(self, token: str) -> PlatformAccessToken | None:
        return await _run(_verify, token)

    async def revoke_token(self, token: PlatformAccessToken | PlatformRefreshToken) -> None:
        await _run(oauth_grants.revoke, token.token_id)

    async def verify_token(self, token: str) -> PlatformAccessToken | None:
        """The SDK's TokenVerifier: every machine token, also one that an officer made, opens /mcp."""
        return await self.load_access_token(token)
