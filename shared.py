import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

from modules.bot.discord_modules.bot import BotFork
from modules.utils.app import app
from modules.utils.config import config
from modules.utils.db import db_connect
from modules.utils.logging_config import logger
from modules.utils.notion import notion
from modules.utils.TokenManager import token_manager as tokenManager

if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        integrations=[FlaskIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        enable_logs=True,
    )
    logger.info("Sentry initialized with logging enabled.")
else:
    logger.warning("SENTRY_DSN not found in environment. Sentry not initialized.")


def create_auth_bot(loop):
    """Create and configure the auth bot (BotFork) instance with a specific event loop."""
    import discord

    logger.info("Creating auth bot instance (BotFork)...")
    intents = discord.Intents.default()
    intents.members = True
    intents.guilds = True

    auth_bot_instance = BotFork(intents=intents, loop=loop)
    try:
        from modules.bot.discord_modules.cogs.GameCog import GameCog
        from modules.bot.discord_modules.cogs.HelperCog import HelperCog

        auth_bot_instance.add_cog(HelperCog(auth_bot_instance))
        auth_bot_instance.add_cog(GameCog(auth_bot_instance))
        logger.info("Auth bot cogs (HelperCog, GameCog) registered with BotFork instance.")
    except Exception as e:
        logger.error(f"Error registering auth bot cogs: {e}", exc_info=True)
    return auth_bot_instance


__all__ = [
    "app",
    "config",
    "db_connect",
    "logger",
    "notion",
    "tokenManager",
    "create_auth_bot",
]
