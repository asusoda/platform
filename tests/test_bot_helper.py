"""The /clear command of HelperCog needs the permissions to delete what it deletes."""

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import discord

from modules.bot.cogs.helper import HelperCog


class _Interaction:
    def __init__(self, permissions: discord.Permissions):
        self.deleted: list[str] = []
        self.sent: list[str] = []
        channel = SimpleNamespace(delete=self._delete("channel"))
        category = SimpleNamespace(name="Jeopardy", channels=[channel], delete=self._delete("category"))
        role = SimpleNamespace(name="Team 1", delete=self._delete("role"))
        self.guild = SimpleNamespace(categories=[category], roles=[role])
        self.user = SimpleNamespace(name="officer", guild_permissions=permissions)
        self.response = SimpleNamespace(send_message=self._send, defer=self._nothing)
        self.followup = SimpleNamespace(send=self._send)

    def _delete(self, kind: str):
        async def delete():
            self.deleted.append(kind)

        return delete

    async def _send(self, message, **kwargs):
        self.sent.append(message)

    async def _nothing(self):
        pass


def _run(permissions: discord.Permissions) -> _Interaction:
    interaction = _Interaction(permissions)
    cog = HelperCog.__new__(HelperCog)
    # The command function, called with the cog and a stand-in for the interaction
    clear: Any = HelperCog.clear.callback
    asyncio.run(clear(cog, interaction))
    return interaction


def test_clear_defaults_to_the_permissions_it_uses():
    wanted = discord.Permissions(manage_guild=True, manage_channels=True, manage_roles=True)
    assert HelperCog.clear.default_member_permissions == wanted


def test_clear_refuses_without_manage_channels_and_roles():
    refused = _run(discord.Permissions(manage_guild=True))
    assert refused.deleted == [] and "Manage Channels" in refused.sent[0]
    refused = _run(discord.Permissions(manage_guild=True, manage_channels=True))
    assert refused.deleted == []
    done = _run(discord.Permissions(manage_guild=True, manage_channels=True, manage_roles=True))
    assert done.deleted == ["channel", "category", "role"]


def test_sign_up_reaction_adds_the_member_to_the_game_of_its_server():
    executed: list[tuple] = []
    bot = SimpleNamespace(user=SimpleNamespace(id=1), execute=lambda *args: executed.append(args))
    cog = HelperCog(cast(Any, bot))
    cog.add_to_listner(cast(Any, SimpleNamespace(id=50)), "✅")
    member = SimpleNamespace(id=7)

    def reaction(user_id, message_id=50, emoji="✅"):
        payload = SimpleNamespace(message_id=message_id, user_id=user_id, guild_id=1001, emoji=emoji, member=member)
        asyncio.run(cog.on_raw_reaction_add(cast(Any, payload)))

    reaction(1)
    reaction(7, message_id=51)
    reaction(7, emoji="❌")
    assert executed == []
    reaction(7)
    assert executed == [("GameCog", "add_member", 1001, member)]
