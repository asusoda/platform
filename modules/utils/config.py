import json
import os

from dotenv import load_dotenv

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


class Config:
    """Centralized configuration management for the application"""

    def __init__(self) -> None:
        load_dotenv()
        try:
            # Core Application Config
            self.SECRET_KEY = os.environ.get("SECRET_KEY", "test-secret-key")
            self.CLIENT_ID = os.environ.get("CLIENT_ID", "test-client-id")
            self.CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "test-client-secret")
            self.REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")
            self.CLIENT_URL = os.environ.get("CLIENT_URL", "http://localhost:3000")
            self.TNAY_API_URL = os.environ.get("TNAY_API_URL", "")
            self.OPEN_ROUTER_CLAUDE_API_KEY = os.environ.get("OPEN_ROUTER_CLAUDE_API_KEY", "")
            self.DISCORD_OFFICER_WEBHOOK_URL = os.environ.get("DISCORD_OFFICER_WEBHOOK_URL", "")
            self.DISCORD_POST_WEBHOOK_URL = os.environ.get("DISCORD_POST_WEBHOOK_URL", "")
            self.DISCORD_STORE_WEBHOOK_URL = os.environ.get("DISCORD_STORE_WEBHOOK_URL", "")
            self.ONEUP_PASSWORD = os.environ.get("ONEUP_PASSWORD", "")
            self.ONEUP_EMAIL = os.environ.get("ONEUP_EMAIL", "")
            self.PROD = os.environ.get("PROD", "false").lower() == "true"

            # Service Tokens
            self.BOT_TOKEN = os.environ.get("BOT_TOKEN")
            self.AVERY_BOT_TOKEN = os.environ.get("AVERY_BOT_TOKEN")
            self.AUTH_BOT_TOKEN = os.environ.get("AUTH_BOT_TOKEN")

            # Auth
            self.CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "test-clerk-secret")
            self.CLERK_AUTHORIZED_PARTIES = os.environ.get(
                "CLERK_AUTHORIZED_PARTIES", "http://localhost:3000,http://localhost:5173"
            )

            # Database Configuration
            self.DB_TYPE = os.environ.get("DB_TYPE", "sqlite")
            self.DB_URI = os.environ.get("DB_URI", "sqlite:///test.db")
            self.DB_NAME = os.environ.get("DB_NAME", "test")
            self.DB_USER = os.environ.get("DB_USER", "test")
            self.DB_PASSWORD = os.environ.get("DB_PASSWORD", "test")
            self.DB_HOST = os.environ.get("DB_HOST", "localhost")
            self.DB_PORT = os.environ.get("DB_PORT", "5432")

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
            self.NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
            self.NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
            self.GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "")
            self.GOOGLE_USER_EMAIL = os.environ.get("GOOGLE_USER_EMAIL", "")
            self.SERVER_PORT = int(os.environ.get("SERVER_PORT", "5000"))
            self.SERVER_DEBUG = os.environ.get("SERVER_DEBUG", "false").lower() == "true"
            self.TIMEZONE = os.environ.get("TIMEZONE", "America/Phoenix")

            # Monitoring Configuration (Optional)
            self.SENTRY_DSN = os.environ.get("SENTRY_DSN")
            self.SYS_ADMIN = os.environ.get("ADMIN_USER_ID")

            # AI Service Keys
            self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

            # Superadmin config
            self.SUPERADMIN_USER_ID = os.environ.get("SYS_ADMIN")

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Configuration error: {str(e)}") from e

    @property
    def google_calendar_config(self) -> dict:
        """Get Google Calendar configuration as a dictionary"""
        return {
            "service_account": self.GOOGLE_SERVICE_ACCOUNT,
            "calendar_id": self.GOOGLE_CALENDAR_ID,
            "user_email": self.GOOGLE_USER_EMAIL,
        }
