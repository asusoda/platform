"""The GitHub integration: an org token for CI runs, app manifests and the github.* tools for agents.

It also holds the org's linked repos (config key dashboard.repos) and the REST reads that the write rule
of the github.* tools needs: a repo's default branch and the checks of a pull request.
"""

from typing import cast

import requests

from core import secrets
from core.integrations.registry import Field, Integration, IntegrationError, register

SECRET_NAME = "github_token"  # nosec B105 - the name of an org secret, not its value
TIMEOUT_SECONDS = 10
API = "https://api.github.com"
# Check conclusions that count as passed
PASSED = {"success", "neutral", "skipped"}


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
                "For the github:write agent tools, also give write access to Contents, Issues and Pull requests.",
            ),
        ),
        docs="modules/runpod-apps",
        test=_test,
    )
)


def linked_repos(org) -> list[str]:
    """The org's linked repos as owner/name, from the config key dashboard.repos."""
    config = cast(dict, org.config) or {}
    return list((config.get("dashboard") or {}).get("repos") or [])


def _get(token: str, path: str, params: dict | None = None) -> dict:
    try:
        response = requests.get(
            f"{API}{path}",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise IntegrationError("GitHub could not be reached") from e
    if response.status_code != 200:
        raise IntegrationError(f"GitHub answered {response.status_code} for {path}")
    body = response.json()
    if not isinstance(body, dict):
        raise IntegrationError(f"GitHub sent an answer that is not an object for {path}")
    return body


def default_branch(token: str, repo: str) -> str:
    return str(_get(token, f"/repos/{repo}").get("default_branch") or "main")


def unmet_checks(token: str, repo: str, number: int) -> str | None:
    """Why the pull request is not ready to merge, or None when it is open and every check passed."""
    pull = _get(token, f"/repos/{repo}/pulls/{number}")
    if pull.get("state") != "open":
        return "the pull request is not open"
    sha = (pull.get("head") or {}).get("sha")
    if not sha:
        return "the pull request has no head commit"
    runs = _get(token, f"/repos/{repo}/commits/{sha}/check-runs", {"per_page": 100}).get("check_runs") or []
    status = _get(token, f"/repos/{repo}/commits/{sha}/status")
    statuses = status.get("statuses") or []
    if not runs and not statuses:
        return "no checks ran on it"
    pending = [r.get("name") for r in runs if r.get("status") != "completed"]
    failed = [r.get("name") for r in runs if r.get("status") == "completed" and r.get("conclusion") not in PASSED]
    failed += [s.get("context") for s in statuses if s.get("state") in ("failure", "error")]
    pending += [s.get("context") for s in statuses if s.get("state") == "pending"]
    if failed:
        return "checks failed: " + ", ".join(str(n) for n in failed)
    if pending:
        return "checks still running: " + ", ".join(str(n) for n in pending)
    return None
