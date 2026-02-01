from flask import Flask, Blueprint, send_from_directory
from flask_cors import CORS
import discord
import os
from modules.utils.db import DBConnect
from notion_client import Client
import asyncio
from modules.utils.config import Config
import logging
from modules.utils.logging_config import logger, get_logger
from modules.utils.db import DBConnect
from modules.utils.base import Base
from modules.utils.TokenManager import TokenManager
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from modules.organizations.models import Organization, OrganizationConfig

# Import custom BotFork class
from modules.bot.discord_modules.bot import BotFork

# Initialize Flask app
app = Flask("SoDA internal API", 
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),
)

# CORS configuration - allow localhost in development only
cors_origins = ["https://thesoda.io", "https://admin.thesoda.io"]
if os.getenv("PROD") == "false":
    cors_origins.extend([
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173"
    ])

CORS(app, 
     resources={r"/*": {
         "origins": cors_origins,
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Content-Type", "Authorization", "X-Organization-ID", "X-Organization-Prefix"],
         "supports_credentials": True
     }},
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
    )
    logger.info("Sentry initialized.")
else:
    logger.warning("SENTRY_DSN not found in environment. Sentry not initialized.")

# Initialize database connections
db_connect = DBConnect("sqlite:///./data/user.db")

# Intialize TokenManager
tokenManger = TokenManager()

# Initialize database connection
db_connect = DBConnect()

# Periodic cleanup of expired refresh tokens
def cleanup_expired_tokens():
    """Clean up expired refresh tokens periodically"""
    try:
        tokenManger.cleanup_expired_refresh_tokens()
        logger.info("Cleaned up expired refresh tokens")
    except Exception as e:
        logger.error(f"Error cleaning up expired tokens: {e}")

# Schedule cleanup every hour
import threading
import time

def run_cleanup_scheduler():
    """Run the cleanup scheduler in a separate thread"""
    while True:
        cleanup_expired_tokens()
        time.sleep(3600)

# Start cleanup scheduler in background thread
cleanup_thread = threading.Thread(target=run_cleanup_scheduler, daemon=True)
cleanup_thread.start()

# Ensure all tables are created after all models are imported
Base.metadata.create_all(bind=db_connect.engine)

def create_auth_bot(loop: asyncio.AbstractEventLoop) -> BotFork: 
    """Create and configure the auth bot (BotFork) instance with a specific event loop."""
    logger.info("Creating auth bot instance (BotFork)...")
    intents = discord.Intents.default()
    intents.members = True
    intents.guilds = True

    auth_bot_instance = BotFork(intents=intents, loop=loop) 
    try:
        from modules.bot.discord_modules.cogs.HelperCog import HelperCog
        from modules.bot.discord_modules.cogs.GameCog import GameCog
        auth_bot_instance.add_cog(HelperCog(auth_bot_instance))
        auth_bot_instance.add_cog(GameCog(auth_bot_instance))
        logger.info("Auth bot cogs (HelperCog, GameCog) registered with BotFork instance.")
    except Exception as e:
        logger.error(f"Error registering auth bot cogs: {e}", exc_info=True)
    return auth_bot_instance

# Initialize Notion client
notion = Client(auth=config.NOTION_API_KEY)

# Initialize bot instance
bot = create_auth_bot(asyncio.get_event_loop())
