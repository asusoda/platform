import asyncio
import os
import secrets
import subprocess  # nosec B404 - subprocess needed for git commit hash retrieval
import threading
from datetime import UTC, datetime

import discord
from flask import Flask, jsonify
from flask_cors import CORS

from core import jobs
from core.config import config
from core.http.audit_hook import register_audit
from core.http.request_log import register_request_logging
from core.integrations.discord import DiscordDirectory
from core.log import get_logger, init_sentry
from modules.auth.tokens import token_manager
from modules.bot.bot import BotFork
from modules.bot.factory import create_bot
from modules.cli import register_cli
from modules.manifest import load_jobs, load_tools
from modules.registry import register_modules

logger = get_logger(__name__)

init_sentry(config.SENTRY_DSN)


class App(Flask):
    """The Flask app with the Discord clients that routes read from current_app."""

    discord_directory: DiscordDirectory
    # Set only while the bot runs in this process (RUN_BOT_IN_API)
    auth_bot: BotFork


app = App(
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
                # Extra origins for other deployments, comma-separated
                *[o.strip() for o in os.environ.get("CORS_EXTRA_ORIGINS", "").split(",") if o.strip()],
                *([os.environ["DASHBOARD_URL"].rstrip("/")] if os.environ.get("DASHBOARD_URL") else []),
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Organization-ID", "X-Organization-Prefix"],
            "supports_credentials": True,
        }
    },
)

# Session cookies are signed with this key. A known default would let anyone forge a session,
# so without FLASK_SECRET_KEY or SECRET_KEY a random key is used and sessions end on restart.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not app.secret_key:
    logger.warning("FLASK_SECRET_KEY is not set; using a random session key until restart")
    app.secret_key = secrets.token_hex(32)

# Officer, member and guild lookups go to Discord's REST API, so the API does not need the bot
app.discord_directory = DiscordDirectory(config.BOT_TOKEN)


def get_git_commit_hash():
    """The commit hash: GIT_COMMIT_HASH from the Docker build, else git rev-parse HEAD."""
    commit_hash = os.environ.get("GIT_COMMIT_HASH")
    if commit_hash:
        return commit_hash

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


COMMIT_HASH = get_git_commit_hash()

STARTUP_TIME = datetime.now(UTC)


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


# Log one structured line per API request
register_request_logging(app, token_manager)

# Record every successful API write in the audit_log table
register_audit(app, token_manager)

register_modules(app)
load_tools()

# Background jobs. On Postgres the worker process (worker_main.py) runs them; on SQLite
# periodic jobs run from a thread here, as the token cleanup always has.
load_jobs()
jobs.start_inline_scheduler()

# `flask --app main org|jobs|config ...`
register_cli(app)


def run_auth_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    auth_bot_instance = create_bot(loop)
    app.auth_bot = auth_bot_instance
    try:
        logger.info("Starting auth bot thread...")
        auth_bot_token = config.BOT_TOKEN
        if not auth_bot_token:
            logger.error("BOT_TOKEN not found. Auth bot will not start.")
            return
        loop.run_until_complete(auth_bot_instance.start(auth_bot_token))
    except discord.errors.LoginFailure:
        logger.error("Login failed for auth bot. Check BOT_TOKEN.")
    except Exception as e:
        logger.error(f"Error in auth bot thread: {e}", exc_info=True)
    finally:
        if loop.is_running() and not auth_bot_instance.is_closed():
            logger.info("Closing auth bot...")
            loop.run_until_complete(auth_bot_instance.close())
        loop.close()
        logger.info("Auth bot thread finished and loop closed.")


def initialize_app():
    is_prod = os.environ.get("IS_PROD", "").lower() == "true"
    use_reloader = not is_prod

    # With the reloader on, Werkzeug executes this file in both a parent (watcher) and a child
    # (server) process. Starting the bot in both logs the same token in twice, so every scheduled
    # post -- the daily LeetCode question in particular -- goes out twice. Only the child, marked
    # by WERKZEUG_RUN_MAIN, owns the bot.
    # In production the bot runs as its own process (bot_main.py) and RUN_BOT_IN_API is false.
    run_bot = os.environ.get("RUN_BOT_IN_API", "true").lower() == "true"
    if not run_bot:
        logger.info("RUN_BOT_IN_API is false; the bot runs in its own process")
    elif not use_reloader or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        auth_thread = threading.Thread(target=run_auth_bot_in_thread, name="AuthBotThread")
        auth_thread.daemon = True
        auth_thread.start()
        logger.info("Auth bot thread initiated")
    else:
        logger.info("Reloader parent process; auth bot will start in the reloaded child process")

    # 0.0.0.0 so the port is reachable from outside the container
    app.run(host="0.0.0.0", port=8000, debug=not is_prod, use_reloader=use_reloader)  # nosec B104


if __name__ == "__main__":
    initialize_app()
