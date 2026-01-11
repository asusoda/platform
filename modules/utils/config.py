import os
import json
from urllib.parse import urlparse
from dotenv import load_dotenv


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_localhost_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0"}

class Config:
    """Centralized configuration management for the application"""
    
    def __init__(self, testing: bool = False) -> None:
        load_dotenv()
        self.testing = testing
        try:
            if testing:
                # Set test defaults for all required variables
                self.SECRET_KEY = os.environ.get("SECRET_KEY", "test-secret-key")
                self.CLIENT_ID = os.environ.get("CLIENT_ID", "test-client-id")
                self.CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "test-client-secret")
                self.REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")
                self.CLIENT_URL = os.environ.get("CLIENT_URL", "http://localhost:3000")
                self.PROD = False
                
                # Service Tokens
                self.BOT_TOKEN = os.environ.get("BOT_TOKEN", "test-bot-token")
                self.AVERY_BOT_TOKEN = os.environ.get("AVERY_BOT_TOKEN", "test-avery-token")
                self.AUTH_BOT_TOKEN = os.environ.get("AUTH_BOT_TOKEN", "test-auth-token")
                
                # Database Configuration
                self.DB_TYPE = os.environ.get("DB_TYPE", "sqlite")
                self.DB_URI = os.environ.get("DB_URI", "sqlite:///test.db")
                self.DB_NAME = os.environ.get("DB_NAME", "test")
                self.DB_USER = os.environ.get("DB_USER", "test") 
                self.DB_PASSWORD = os.environ.get("DB_PASSWORD", "test")
                self.DB_HOST = os.environ.get("DB_HOST", "localhost")
                self.DB_PORT = os.environ.get("DB_PORT", "5432")
                
                # Google service account - use dummy data for tests
                self.GOOGLE_SERVICE_ACCOUNT = {"type": "service_account", "project_id": "test"}
                
                self.NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "test-notion-key")
                self.NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "test-db-id")
                self.NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "test-notion-token")
                self.GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "test@calendar.google.com")
                self.GOOGLE_USER_EMAIL = os.environ.get("GOOGLE_USER_EMAIL", "test@example.com")
                self.SERVER_PORT = 5000
                self.SERVER_DEBUG = True
                self.TIMEZONE = "America/Phoenix"
                
                # Optional configs
                self.SENTRY_DSN = None
                self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "test-gemini-key")

                # Superadmin config
                self.SUPERADMIN_USER_ID = os.environ.get("SYS_ADMIN", "test-superadmin-id")
            else:
                # Environment mode detection
                # Requirement: if IS_PROD is false OR debug/dev, force localhost redirects.
                is_prod_env = os.environ.get("IS_PROD")
                flask_env = os.environ.get("FLASK_ENV", "").lower()
                flask_debug = os.environ.get("FLASK_DEBUG", "0") == "1"

                # If IS_PROD is explicitly set, it wins.
                # Otherwise, infer production from FLASK_ENV and FLASK_DEBUG.
                self.PROD = _is_truthy(is_prod_env) if is_prod_env is not None else (flask_env == "production" and not flask_debug)

                def _require_env(name: str) -> str:
                    value = os.environ.get(name)
                    if value is None or value == "":
                        raise KeyError(name)
                    return value

                # Core Application Config
                # In production we keep strict requirements. In dev, we allow sensible defaults.
                self.SECRET_KEY = _require_env("SECRET_KEY") if self.PROD else os.environ.get("SECRET_KEY", "dev-secret-key")
                self.CLIENT_ID = _require_env("CLIENT_ID") if self.PROD else os.environ.get("CLIENT_ID", "")
                self.CLIENT_SECRET = _require_env("CLIENT_SECRET") if self.PROD else os.environ.get("CLIENT_SECRET", "")

                # Redirect + UI URLs
                dev_client_url = os.environ.get("DEV_CLIENT_URL")
                dev_redirect_uri = os.environ.get("DEV_REDIRECT_URI")
                env_client_url = os.environ.get("CLIENT_URL")
                env_redirect_uri = os.environ.get("REDIRECT_URI")

                if self.PROD:
                    self.CLIENT_URL = _require_env("CLIENT_URL")
                    self.REDIRECT_URI = _require_env("REDIRECT_URI")
                else:
                    # Force localhost redirects in dev/debug (even if .env contains production domains)
                    self.CLIENT_URL = dev_client_url or env_client_url or "http://localhost:5000"
                    self.REDIRECT_URI = dev_redirect_uri or env_redirect_uri or "http://localhost:8000/api/auth/callback"
                    if not _is_localhost_url(self.CLIENT_URL):
                        self.CLIENT_URL = "http://localhost:5000"
                    if not _is_localhost_url(self.REDIRECT_URI):
                        self.REDIRECT_URI = "http://localhost:8000/api/auth/callback"

                # Misc URLs / keys (required in prod, optional in dev)
                self.TNAY_API_URL = _require_env("TNAY_API_URL") if self.PROD else os.environ.get("TNAY_API_URL", "")
                self.OPEN_ROUTER_CLAUDE_API_KEY = _require_env("OPEN_ROUTER_CLAUDE_API_KEY") if self.PROD else os.environ.get("OPEN_ROUTER_CLAUDE_API_KEY", "")
                self.DISCORD_OFFICER_WEBHOOK_URL = _require_env("DISCORD_OFFICER_WEBHOOK_URL") if self.PROD else os.environ.get("DISCORD_OFFICER_WEBHOOK_URL", "")
                self.DISCORD_POST_WEBHOOK_URL = _require_env("DISCORD_POST_WEBHOOK_URL") if self.PROD else os.environ.get("DISCORD_POST_WEBHOOK_URL", "")
                self.ONEUP_PASSWORD = _require_env("ONEUP_PASSWORD") if self.PROD else os.environ.get("ONEUP_PASSWORD", "")
                self.ONEUP_EMAIL = _require_env("ONEUP_EMAIL") if self.PROD else os.environ.get("ONEUP_EMAIL", "")

                # Service Tokens
                self.BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Legacy token
                self.AVERY_BOT_TOKEN = os.environ.get("AVERY_BOT_TOKEN")  # AVERY bot token
                self.AUTH_BOT_TOKEN = os.environ.get("AUTH_BOT_TOKEN")  # Auth bot token
                
                # Database Configuration
                self.DB_TYPE = _require_env("DB_TYPE") if self.PROD else os.environ.get("DB_TYPE", "sqlite")
                self.DB_URI = _require_env("DB_URI") if self.PROD else os.environ.get("DB_URI", "sqlite:///./data/user.db")
                self.DB_NAME = _require_env("DB_NAME") if self.PROD else os.environ.get("DB_NAME", "dev")
                self.DB_USER = _require_env("DB_USER") if self.PROD else os.environ.get("DB_USER", "")
                self.DB_PASSWORD = _require_env("DB_PASSWORD") if self.PROD else os.environ.get("DB_PASSWORD", "")
                self.DB_HOST = _require_env("DB_HOST") if self.PROD else os.environ.get("DB_HOST", "localhost")
                self.DB_PORT = _require_env("DB_PORT") if self.PROD else os.environ.get("DB_PORT", "5432")
                # Calendar Integration

                try:
                    with open("google-secret.json", "r") as file:
                        print("Loading Google service account credentials")
                        self.GOOGLE_SERVICE_ACCOUNT = json.load(file)
                        print("Google service account credentials loaded successfully")
                        # Redact sensitive information
                        masked_credentials = {
                            **self.GOOGLE_SERVICE_ACCOUNT,
                            "private_key": "[REDACTED]"
                        } if self.GOOGLE_SERVICE_ACCOUNT else None
                        print("Google service account credentials loaded")
                except FileNotFoundError:
                    print("Warning: google-secret.json not found. Google Calendar features will be disabled.")
                    self.GOOGLE_SERVICE_ACCOUNT = None
                except Exception as e:
                    print(f"Warning: Error loading Google credentials: {e}. Google Calendar features will be disabled.")
                    self.GOOGLE_SERVICE_ACCOUNT = None
                    
                self.NOTION_API_KEY = _require_env("NOTION_API_KEY") if self.PROD else os.environ.get("NOTION_API_KEY", "")
                self.NOTION_DATABASE_ID = _require_env("NOTION_DATABASE_ID") if self.PROD else os.environ.get("NOTION_DATABASE_ID", "")
                self.GOOGLE_CALENDAR_ID = _require_env("GOOGLE_CALENDAR_ID") if self.PROD else os.environ.get("GOOGLE_CALENDAR_ID", "")
                self.GOOGLE_USER_EMAIL = _require_env("GOOGLE_USER_EMAIL") if self.PROD else os.environ.get("GOOGLE_USER_EMAIL", "")
                self.SERVER_PORT = int(os.environ.get("SERVER_PORT", "5000"))
                self.SERVER_DEBUG = os.environ.get("SERVER_DEBUG", "false").lower() == "true"
                self.TIMEZONE = os.environ.get("TIMEZONE", "America/Phoenix")

                # Monitoring Configuration (Optional)
                self.SENTRY_DSN = os.environ.get("SENTRY_DSN")
                self.SYS_ADMIN = os.environ.get("ADMIN_USER_ID")
                # AI Service Keys
                self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
                self.NOTION_TOKEN = os.environ.get("NOTION_TOKEN")

                # Superadmin config
                self.SUPERADMIN_USER_ID = os.environ.get("SYS_ADMIN")

        except (KeyError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Configuration error: {str(e)}") from e

    @property
    def google_calendar_config(self) -> dict:
        """Get Google Calendar configuration as a dictionary"""
        return {
            "service_account": self.GOOGLE_SERVICE_ACCOUNT,
            "calendar_id": self.GOOGLE_CALENDAR_ID,
            "user_email": self.GOOGLE_USER_EMAIL
        }