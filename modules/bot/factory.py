"""Builds the Discord bot with its cogs."""

import asyncio

import discord

from core.db import db_connect
from core.log import get_logger
from modules.bot.bot import BotFork
from modules.bot.cogs.helper import HelperCog
from modules.games.cog import GameCog
from modules.leetcode.cog import LeetCodeCog

logger = get_logger(__name__)


def create_bot(loop: asyncio.AbstractEventLoop) -> BotFork:
    """The bot on the given event loop, with HelperCog, GameCog and LeetCodeCog added."""
    intents = discord.Intents.default()
    intents.members = True
    intents.guilds = True

    bot = BotFork(intents=intents, loop=loop)
    try:
        bot.add_cog(HelperCog(bot))
        bot.add_cog(GameCog(bot))
        bot.add_cog(LeetCodeCog(bot=bot, db_connect=db_connect))
        logger.info("Bot cogs registered: HelperCog, GameCog, LeetCodeCog")
    except Exception as e:
        logger.error(f"Error registering bot cogs: {e}", exc_info=True)
    return bot
