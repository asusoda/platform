from flask import Flask, Blueprint, send_from_directory
from flask_cors import CORS
import discord
import os
from modules.utils.db import DBConnect, OCPDBManager
from notion_client import Client
import asyncio
from modules.utils.config import Config
# from modules.utils.db import DBManager
import logging
# Import the logger from our dedicated logging module
from modules.utils.logging_config import logger, get_logger
from modules.utils.db import DBConnect, Base
from modules.utils.TokenManager import TokenManager
import sentry_sdk # Added for Sentry
from sentry_sdk.integrations.flask import FlaskIntegration # Added for Sentry

# Import custom BotFork class
from modules.bot.discord_modules.bot import BotFork

# Initialize Flask app
app = Flask("SoDA internal API", 
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),  # Path to built frontend files
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),  # Path to built frontend files
)
CORS(app, 
     resources={r"/*": {"origins": "*"}},
)

# Initialize configuration
config = Config()

# Initialize Sentry (ensure SENTRY_DSN is set in your environment)
if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        integrations=[FlaskIntegration()],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # Adjust lower for production.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions. Adjust lower for production.
        profiles_sample_rate=1.0,
        # Consider adding environment='development' or 'production'
        # environment=config.FLASK_ENV or 'production' # Example
    )
    logger.info("Sentry initialized.")
else:
    logger.warning("SENTRY_DSN not found in environment. Sentry not initialized.")

# Initialize database connections
db_connect = DBConnect("sqlite:///./data/user.db")
tokenManger = TokenManager()

# Initialize OCP database manager (tables will be created automatically if they don't exist)
try:
    
    # Initialize the OCP database manager
    ocp_db_manager = OCPDBManager("sqlite:///./data/ocp.db")
    logger.info("OCP database manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OCP database manager: {str(e)}")
    logger.warning("OCP functionality will be limited. Individual services will create their own database connections if needed.")
    ocp_db_manager = None

def create_summarizer_bot(loop: asyncio.AbstractEventLoop) -> discord.Bot:
    """Create and configure the summarizer bot instance with a specific event loop."""
    logger.info("Creating summarizer bot instance (standard discord.Bot)...")
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guild_messages = True

    # Summarizer bot can remain a standard discord.Bot if it doesn't need BotFork features
    summarizer_bot_instance = discord.Bot(intents=intents, loop=loop)
    try:
        from modules.summarizer.discord_modules.setup import setup_summarizer_cog
        setup_summarizer_cog(summarizer_bot_instance)
        logger.info("Summarizer cog registered with summarizer_bot_instance.")
    except Exception as e:
        logger.error(f"Error registering summarizer cog: {e}", exc_info=True)
    return summarizer_bot_instance

def create_auth_bot(loop: asyncio.AbstractEventLoop) -> BotFork: 
    """Create and configure the auth bot (BotFork) instance with a specific event loop."""
    logger.info("Creating auth bot instance (BotFork)...")
    intents = discord.Intents.default()
    intents.members = True
    intents.guilds = True

    # Use BotFork for the auth_bot_instance
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

# Initialize both bot instances
summarizer_bot = create_summarizer_bot(asyncio.get_event_loop())
auth_bot = create_auth_bot(asyncio.get_event_loop())

# Note: The global 'bot' variable that was previously an alias for auth_bot
# is removed. API endpoints will need to access the auth_bot via Flask's app context.
