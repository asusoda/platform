"""The game announcement names the org on the game's server, or the server itself."""

from types import SimpleNamespace
from typing import cast

import discord


def test_announcement_location_names_the_org_or_the_server(app):
    from modules.games.cog import server_name

    assert server_name(cast(discord.Guild, SimpleNamespace(id=1002, name="Guild Name"))) == "AI Society"
    assert server_name(cast(discord.Guild, SimpleNamespace(id=9999, name="Guild Name"))) == "Guild Name"
