"""Send Discord messages and reactions over the REST API with the bot token, without the gateway bot."""

from urllib.parse import quote

import requests

from core.discord_directory import API, DiscordUnavailable


def _call(method: str, path: str, token: str | None, payload: dict | None = None) -> dict:
    if not token:
        raise DiscordUnavailable("BOT_TOKEN is not set")
    try:
        response = requests.request(
            method, f"{API}{path}", json=payload, headers={"Authorization": f"Bot {token}"}, timeout=10
        )
    except requests.RequestException as e:
        raise DiscordUnavailable(str(e)) from e
    if response.status_code >= 300:
        raise DiscordUnavailable(f"{method} {path} returned {response.status_code}")
    return response.json() if response.content else {}


def send_message(token: str | None, channel_id: int | str, payload: dict) -> dict:
    """Post a message (content, embeds, message_reference) to a channel. Returns the message."""
    return _call("POST", f"/channels/{int(channel_id)}/messages", token, payload)


def add_reaction(token: str | None, channel_id: int | str, message_id: int | str, emoji: str) -> None:
    _call("PUT", f"/channels/{int(channel_id)}/messages/{int(message_id)}/reactions/{quote(emoji)}/@me", token)
