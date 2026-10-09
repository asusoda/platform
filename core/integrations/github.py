"""The GitHub integration: an org token for CI runs, app manifests and the github.* tools for agents."""

import requests

from core import secrets
from core.integrations.registry import Field, Integration, IntegrationError, register

SECRET_NAME = "github_token"  # nosec B105 - the name of an org secret, not its value
TIMEOUT_SECONDS = 10


def _test(db, org_id: int) -> str:
    token = secrets.get_secret(db, org_id, SECRET_NAME)
    if not token:
        raise IntegrationError("Set a GitHub token first. Public repos work without one")
    try:
        response = requests.get(
            "https://api.github.com/rate_limit",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise IntegrationError("GitHub could not be reached") from e
    if response.status_code == 401:
        raise IntegrationError("GitHub refused the token")
    if response.status_code != 200:
        raise IntegrationError(f"GitHub answered {response.status_code}")
    remaining = response.json().get("resources", {}).get("core", {}).get("remaining")
    return f"Connected. {remaining} API calls left this hour." if remaining is not None else "Connected."


register(
    Integration(
        key="github",
        title="GitHub",
        description="Connect the org's GitHub repos: CI runs, app manifests, and GitHub tools for agents.",
        fields=(
            Field(
                SECRET_NAME,
                "Access token",
                "A fine-grained token. Read access to Actions and Contents is enough for CI and apps. "
                "For the github:write agent tools, also give write access to Issues and Pull requests.",
            ),
        ),
        docs="modules/runpod-apps",
        test=_test,
    )
)
