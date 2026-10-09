"""The Notion and Google integrations that calendar sync reads. No Flask here."""

import json

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from core import secrets
from core.config import config
from core.integrations.registry import Field, Integration, IntegrationError, register, use

NOTION_SECRET = "notion_api_key"  # nosec B105 - the name of an org secret, not its value
GOOGLE_SECRET = "google_service_account"  # nosec B105 - the name of an org secret, not its value
GOOGLE_SUBJECT = "google_subject"
TIMEOUT_SECONDS = 10
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def _notion_test(db, org_id: int) -> str:
    token = secrets.get_secret(db, org_id, NOTION_SECRET) or config.NOTION_API_KEY
    if not token:
        raise IntegrationError("Set a Notion token first")
    try:
        response = requests.get(
            "https://api.notion.com/v1/users/me",
            headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise IntegrationError("Notion could not be reached") from e
    if response.status_code == 401:
        raise IntegrationError("Notion refused the token")
    if response.status_code != 200:
        raise IntegrationError(f"Notion answered {response.status_code}")
    name = response.json().get("name")
    return f"Connected as {name}." if name else "Connected."


def _google_test(db, org_id: int) -> str:
    raw = secrets.get_secret(db, org_id, GOOGLE_SECRET)
    try:
        info = json.loads(raw) if raw else config.GOOGLE_SERVICE_ACCOUNT
    except ValueError as e:
        raise IntegrationError("The service account key is not JSON") from e
    if not isinstance(info, dict) or not info.get("client_email"):
        raise IntegrationError("Set a Google service account key first")
    subject = secrets.get_secret(db, org_id, GOOGLE_SUBJECT) if raw else None
    try:
        credentials = service_account.Credentials.from_service_account_info(info, scopes=[CALENDAR_SCOPE])
        if subject:
            credentials = credentials.with_subject(subject)
        credentials.refresh(Request())
    except (GoogleAuthError, ValueError) as e:
        if subject:
            raise IntegrationError(f"Google refused to let the service account act as {subject}") from e
        raise IntegrationError("Google refused the service account key") from e
    if subject:
        return f"Connected as {info['client_email']}, acting as {subject}."
    return f"Connected as {info['client_email']}."


register(
    Integration(
        key="notion",
        title="Notion",
        description="Connect the org's Notion workspace.",
        fields=(
            Field(
                NOTION_SECRET,
                "Integration token",
                "Notion > Settings > Integrations. Share the events database with the integration.",
            ),
        ),
        docs="modules/calendar",
        deployment=lambda: bool(config.NOTION_API_KEY),
        test=_notion_test,
    )
)
register(
    Integration(
        key="google",
        title="Google",
        description="Connect a Google Cloud service account for the org: Calendar sync and Google tools for agents.",
        fields=(
            Field(
                GOOGLE_SECRET,
                "Service account key",
                "The JSON key of a Google Cloud service account with the Calendar, Drive, Sheets and Gmail APIs on.",
                kind="json",
            ),
            Field(
                GOOGLE_SUBJECT,
                "Act as Workspace user",
                "Optional. A user email in your Google Workspace. The service account then acts as this user "
                "through domain-wide delegation. Gmail tools need it.",
                secret=False,
                optional=True,
            ),
        ),
        docs="modules/calendar",
        deployment=lambda: bool(config.GOOGLE_SERVICE_ACCOUNT),
        test=_google_test,
    )
)
use("notion", "calendar")
use("google", "calendar")
