"""The Sentry integration: a read-only auth token that lists a project's issues in the dashboard."""

from typing import Any

import requests

from core.integrations.registry import Field, Integration, IntegrationError, org_values, register

KEY = "sentry"
TOKEN = "sentry_auth_token"  # nosec B105 - the name of an org secret, not its value
ORG = "sentry_org"
PROJECT = "sentry_project"
URL = "sentry_url"
DEFAULT_URL = "https://sentry.io"
TIMEOUT_SECONDS = 10


class SentryError(IntegrationError):
    """Sentry refused or failed a request. The message has no secret in it."""


def settings(db, org_id: int) -> dict[str, str] | None:
    """The org's Sentry token, org slug, project slug and base URL, or None when not set."""
    values = org_values(db, org_id, KEY)
    if values is None:
        return None
    return {
        "token": values[TOKEN],
        "org": values[ORG],
        "project": values[PROJECT],
        "url": (values.get(URL) or DEFAULT_URL).rstrip("/"),
    }


def get(conf: dict[str, str], path: str, params: dict | None = None) -> Any:
    """GET a Sentry API path for the configured project and return the JSON body."""
    try:
        response = requests.get(
            f"{conf['url']}/api/0/projects/{conf['org']}/{conf['project']}/{path}",
            params=params,
            headers={"Authorization": f"Bearer {conf['token']}"},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise SentryError("Sentry could not be reached") from e
    if response.status_code in (401, 403):
        raise SentryError("Sentry refused the token. It needs the project:read and event:read scopes")
    if response.status_code == 404:
        raise SentryError("Sentry has no project with this org and project slug")
    if response.status_code != 200:
        raise SentryError(f"Sentry answered {response.status_code}")
    return response.json()


def _test(db, org_id: int) -> str:
    conf = settings(db, org_id)
    if conf is None:
        raise IntegrationError("Set the auth token, org slug and project slug first")
    project = get(conf, "")
    name = project.get("name") if isinstance(project, dict) else None
    return f"Connected to project {name}." if name else "Connected."


register(
    Integration(
        key=KEY,
        title="Sentry",
        description="Connect the org's Sentry project.",
        fields=(
            Field(TOKEN, "Auth token", "An internal integration or user auth token with project:read and event:read."),
            Field(ORG, "Org slug", "The organization slug in the Sentry URL.", secret=False),
            Field(PROJECT, "Project slug", "The project that gets the errors.", secret=False),
            Field(
                URL,
                "Sentry URL",
                "Only for self-hosted Sentry or a regional host. Default https://sentry.io.",
                kind="url",
                secret=False,
                optional=True,
            ),
        ),
        docs="integrations",
        test=_test,
    )
)
