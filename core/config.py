import json
import os

from dotenv import load_dotenv

from core.logging_config import get_logger

logger = get_logger(__name__)


class Config:
    """Centralized configuration management for the application"""

    def __init__(self) -> None:
        load_dotenv()
        try:
            # Core Application Config
            self.CLIENT_ID = os.environ.get("CLIENT_ID", "test-client-id")
            self.CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "test-client-secret")
            self.REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")
            self.CLIENT_URL = os.environ.get("CLIENT_URL", "http://localhost:3000")
            # Officer dashboard (dashboard/). Login sends officers back here when they start from it
            self.DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "").rstrip("/")

            # Service Tokens
            self.BOT_TOKEN = os.environ.get("BOT_TOKEN")

            # Auth
            self.CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "test-clerk-secret")
            self.CLERK_AUTHORIZED_PARTIES = os.environ.get(
                "CLERK_AUTHORIZED_PARTIES", "http://localhost:3000,http://localhost:5173"
            )

            # Google Calendar Integration
            try:
                with open("google-secret.json") as file:
                    self.GOOGLE_SERVICE_ACCOUNT = json.load(file)
                    logger.info("Google service account credentials loaded successfully")
            except FileNotFoundError:
                logger.warning("google-secret.json not found. Google Calendar features will be disabled.")
                self.GOOGLE_SERVICE_ACCOUNT = None
            except Exception as e:
                logger.warning(f"Error loading Google credentials: {e}. Google Calendar features will be disabled.")
                self.GOOGLE_SERVICE_ACCOUNT = None

            self.NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
            self.TIMEZONE = os.environ.get("TIMEZONE", "America/Phoenix")

            # Monitoring Configuration (Optional)
            self.SENTRY_DSN = os.environ.get("SENTRY_DSN")

            # Superadmin config: the Discord user id in SYS_ADMIN
            self.SUPERADMIN_USER_ID = os.environ.get("SYS_ADMIN")

            # Access checks (modules/auth/access.py): false logs refusals, true enforces them
            self.ACCESS_ENFORCE = os.environ.get("ACCESS_ENFORCE", "false").lower() == "true"

            # Compute (modules/compute): the CLI name members see in messages, and the default pod image
            self.COMPUTE_CLI_NAME = os.environ.get("COMPUTE_CLI_NAME", "the compute CLI")
            self.COMPUTE_POD_IMAGE = os.environ.get("COMPUTE_POD_IMAGE", "theaisocietyasu/godfather-base:latest")

            # LeetCode Daily Bot
            self.LEETCODE_CHANNEL_ID = os.environ.get("LEETCODE_CHANNEL_ID")
            self.LEETCODE_ROLE_PING = os.environ.get("LEETCODE_ROLE_PING")
            self.LEETCODE_DAILY_TIME = os.environ.get("LEETCODE_DAILY_TIME", "09:00")

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Configuration error: {str(e)}") from e
