import asyncio
import os

import discord
import sentry_sdk
from flask import Flask
from flask_cors import CORS
from notion_client import Client
from sentry_sdk.integrations.flask import FlaskIntegration

from core.config import Config
from core.db import DBConnect
from core.logging_config import logger
from core.TokenManager import TokenManager

# Import custom BotFork class
from modules.bot.discord_modules.bot import BotFork

# Initialize Flask app
app = Flask(
    "SoDA internal API",
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),
)
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "https://thesoda.io",
                "https://admin.thesoda.io",
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Organization-ID", "X-Organization-Prefix"],
            "supports_credentials": True,
        }
    },
)

# Initialize configuration
config = Config()

# Initialize Sentry
if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        integrations=[FlaskIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        # Enable logs to be sent to Sentry
        enable_logs=True,
    )
    logger.info("Sentry initialized with logging enabled.")
else:
    logger.warning("SENTRY_DSN not found in environment. Sentry not initialized.")

# Initialize database connections
db_connect = DBConnect(os.environ.get("DATABASE_URL", "sqlite:///./data/user.db"))

# Initialize TokenManager
tokenManager = TokenManager()


def create_auth_bot(loop: asyncio.AbstractEventLoop) -> BotFork:
    """Create and configure the auth bot (BotFork) instance with a specific event loop."""
    logger.info("Creating auth bot instance (BotFork)...")
    intents = discord.Intents.default()
    intents.members = True
    intents.guilds = True

    auth_bot_instance = BotFork(intents=intents, loop=loop)
    try:
        from modules.bot.discord_modules.cogs.GameCog import GameCog
        from modules.bot.discord_modules.cogs.HelperCog import HelperCog
        from modules.bot.discord_modules.cogs.LeetCodeCog import LeetCodeCog

        auth_bot_instance.add_cog(HelperCog(auth_bot_instance))
        auth_bot_instance.add_cog(GameCog(auth_bot_instance))

        lc_channel_id: int | None = None
        lc_role_ping: int | None = None
        if config.LEETCODE_CHANNEL_ID:
            try:
                lc_channel_id = int(config.LEETCODE_CHANNEL_ID)
            except ValueError:
                logger.warning(
                    f"Invalid LEETCODE_CHANNEL_ID '{config.LEETCODE_CHANNEL_ID}', daily task will be skipped"
                )
        if config.LEETCODE_ROLE_PING:
            try:
                lc_role_ping = int(config.LEETCODE_ROLE_PING)
            except ValueError:
                logger.warning(f"Invalid LEETCODE_ROLE_PING '{config.LEETCODE_ROLE_PING}', role ping will be skipped")

        auth_bot_instance.add_cog(
            LeetCodeCog(
                bot=auth_bot_instance,
                db_connect=db_connect,
                channel_id=lc_channel_id,
                role_ping=lc_role_ping,
                daily_time=config.LEETCODE_DAILY_TIME,
                timezone=config.TIMEZONE,
            )
        )
        logger.info("Auth bot cogs (HelperCog, GameCog, LeetCodeCog) registered with BotFork instance.")
    except Exception as e:
        logger.error(f"Error registering auth bot cogs: {e}", exc_info=True)
    return auth_bot_instance


# Initialize Notion client
notion = Client(auth=config.NOTION_API_KEY)
