"""The public URL of the API, the Google OAuth app, and the Discord sign-in that proves who a browser belongs to.

ACCOUNTS_BASE_URL is the public URL of this API; OAuth providers send the browser back to it. The Google app is on
when ACCOUNTS_GOOGLE_CLIENT_ID and ACCOUNTS_GOOGLE_CLIENT_SECRET are set. MCP OAuth, the integrations sign-in and
the Godfather CLI sign-in use these.
"""

import os
from dataclasses import dataclass
from urllib.parse import urlencode

import requests

TIMEOUT_SECONDS = 30

DISCORD_AUTHORIZE = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN = "https://discord.com/api/v10/oauth2/token"  # nosec B105 - a URL, not a password
DISCORD_ME = "https://discord.com/api/v10/users/@me"


class SignInError(RuntimeError):
    """A sign-in request to Discord failed."""


@dataclass(frozen=True)
class GoogleApp:
    client_id: str
    client_secret: str


def base_url() -> str:
    """ACCOUNTS_BASE_URL with no trailing slash, or "" when it is not set."""
    return os.environ.get("ACCOUNTS_BASE_URL", "").strip().rstrip("/")


def google_app() -> GoogleApp | None:
    """The Google OAuth app, when the public URL and both of its settings are set."""
    client_id = os.environ.get("ACCOUNTS_GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("ACCOUNTS_GOOGLE_CLIENT_SECRET", "").strip()
    if not base_url() or not client_id or not client_secret:
        return None
    return GoogleApp(client_id, client_secret)


def discord_consent_url(client_id: str, state: str, redirect_uri: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify",
        "state": state,
        "prompt": "none",
    }
    return f"{DISCORD_AUTHORIZE}?{urlencode(params)}"


def discord_user_id(client_id: str, client_secret: str, code: str, redirect_uri: str) -> str:
    """The Discord user id behind an authorization code."""
    form = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    try:
        token = requests.post(DISCORD_TOKEN, data=form, timeout=TIMEOUT_SECONDS)
        token.raise_for_status()
        access = token.json()["access_token"]
        me = requests.get(DISCORD_ME, headers={"Authorization": f"Bearer {access}"}, timeout=TIMEOUT_SECONDS)
        me.raise_for_status()
        return str(me.json()["id"])
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        raise SignInError("Discord sign-in failed") from e
