import asyncio
import os
import subprocess  # nosec B404 - subprocess needed for git commit hash retrieval
import threading
from datetime import UTC, datetime

import discord
from flask import jsonify  # Import current_app

from modules.auth.api import auth_blueprint
from modules.bot.api import game_blueprint
from modules.calendar.api import calendar_blueprint
from modules.calendar.service import MultiOrgCalendarService
from modules.organizations.api import organizations_blueprint
from modules.points.api import points_blueprint
from modules.public.api import public_blueprint
from modules.storefront.api import storefront_blueprint
from modules.superadmin.api import superadmin_blueprint
from modules.users.api import users_blueprint
from shared import app, config, create_auth_bot, logger

# Set a secret key for session management
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

# Initialize multi-organization calendar service
multi_org_calendar_service = MultiOrgCalendarService(logger)
app.multi_org_calendar_service = multi_org_calendar_service


def get_git_commit_hash():
    """Get the current git commit hash."""
    # First check if commit hash is provided via environment variable (set during Docker build)
    commit_hash = os.environ.get("GIT_COMMIT_HASH")
    if commit_hash:
        return commit_hash

    # Fall back to git command (for local development)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # nosec B603, B607 - hardcoded git command with no user input
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


# Cache the commit hash at startup since it won't change during runtime
COMMIT_HASH = get_git_commit_hash()

# Record the startup time (container creation/start time)
STARTUP_TIME = datetime.now(UTC)


# Health endpoint
@app.route("/health")
def health():
    return jsonify(
        {
            "status": "healthy",
            "service": "soda-internal-api",
            "commit": COMMIT_HASH,
            "started_at": STARTUP_TIME.isoformat(),
        }
    ), 200


# Register Blueprints
app.register_blueprint(public_blueprint, url_prefix="/api/public")
app.register_blueprint(points_blueprint, url_prefix="/api/points")
app.register_blueprint(users_blueprint, url_prefix="/api/users")
app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
app.register_blueprint(calendar_blueprint, url_prefix="/api/calendar")
app.register_blueprint(game_blueprint, url_prefix="/api/bot")
app.register_blueprint(organizations_blueprint, url_prefix="/api/organizations")
app.register_blueprint(superadmin_blueprint, url_prefix="/api/superadmin")
app.register_blueprint(storefront_blueprint, url_prefix="/api/storefront")
# # Configure static file serving
# @app.route('/', defaults={'path': ''})
# @app.route('/<path:path>')
# def serve(path):
#     if path == "":
#         return send_from_directory('web/dist', 'index.html')
#     else:
#         return send_from_directory('web/dist', path)


# --- Bot Thread Functions ---
def run_auth_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Create bot instance inside the thread, using the thread's loop
    auth_bot_instance = create_auth_bot(loop)
    # Store the auth_bot instance on the Flask app context for API use
    app.auth_bot = auth_bot_instance
    try:
        logger.info("Starting auth bot thread...")
        auth_bot_token = config.BOT_TOKEN
        if not auth_bot_token:
            logger.error("BOT_TOKEN not found. Auth bot will not start.")
            return
        # Use bot_instance.start() and manage the loop
        loop.run_until_complete(auth_bot_instance.start(auth_bot_token))
    except discord.errors.LoginFailure:
        logger.error("Login failed for auth bot. Check AUTH_BOT_TOKEN.")
    except Exception as e:
        logger.error(f"Error in auth bot thread: {e}", exc_info=True)
    finally:
        if loop.is_running() and not auth_bot_instance.is_closed():
            logger.info("Closing auth bot...")
            loop.run_until_complete(auth_bot_instance.close())
        loop.close()
        logger.info("Auth bot thread finished and loop closed.")


# --- App Initialization ---
def initialize_app():
    auth_thread = threading.Thread(target=run_auth_bot_in_thread, name="AuthBotThread")
    auth_thread.daemon = True
    auth_thread.start()
    logger.info("Auth bot thread initiated")

    # Start Flask app
    # Enable debug and reloader based on IS_PROD environment variable
    is_prod = os.environ.get("IS_PROD", "").lower() == "true"
    # Binding to 0.0.0.0 is required for Docker container accessibility
    app.run(host="0.0.0.0", port=8000, debug=not is_prod, use_reloader=not is_prod)  # nosec B104


if __name__ == "__main__":
    initialize_app()
