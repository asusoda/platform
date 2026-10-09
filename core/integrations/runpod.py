"""RunPod REST client (api.runpod.io/v2). Each org uses its own API key, stored as an org secret."""

from typing import Any
from urllib.parse import quote

import requests

from core import secrets
from core.integrations.registry import Field, Integration, IntegrationError, register
from core.log import get_logger

logger = get_logger("runpod")

BASE_URL = "https://api.runpod.io/v2"
TIMEOUT_SECONDS = 30
SECRET_NAME = "runpod_api_key"  # nosec B105 - the name of an org secret, not its value


class RunPodError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status


class RunPodClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        try:
            response = requests.request(
                method,
                self._base_url + path,
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            raise RunPodError("RunPod could not be reached") from e
        if response.status_code >= 400:
            try:
                detail = str(response.json().get("error") or response.json().get("message") or "")[:300]
            except (ValueError, AttributeError):
                detail = ""
            logger.warning("runpod %s %s failed status=%s %s", method, path, response.status_code, detail)
            raise RunPodError(f"RunPod answered {response.status_code}: {detail}".rstrip(": "), response.status_code)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as e:
            raise RunPodError("RunPod sent a response that is not JSON") from e

    def get_pod(self, pod_id: str) -> dict | None:
        try:
            return self._request("GET", f"/pods/{quote(pod_id, safe='')}")
        except RunPodError as e:
            if e.status == 404:
                return None
            raise

    def create_pod(self, body: dict) -> dict:
        return self._request("POST", "/pods", body)

    def update_pod(self, pod_id: str, body: dict) -> dict:
        return self._request("PATCH", f"/pods/{quote(pod_id, safe='')}", body)

    def start_pod(self, pod_id: str) -> Any:
        return self._request("POST", f"/pods/{quote(pod_id, safe='')}/start")

    def stop_pod(self, pod_id: str) -> Any:
        return self._request("POST", f"/pods/{quote(pod_id, safe='')}/stop")

    def delete_pod(self, pod_id: str) -> Any:
        return self._request("DELETE", f"/pods/{quote(pod_id, safe='')}")


def proxy_url(pod_id: str, port: int, path: str) -> str:
    """The public HTTPS address RunPod gives an http port of a pod."""
    return f"https://{pod_id}-{port}.proxy.runpod.net{path}"


def _test(db, org_id: int) -> str:
    key = secrets.get_secret(db, org_id, SECRET_NAME)
    if not key:
        raise IntegrationError("Set the RunPod API key first")
    try:
        pods = RunPodClient(key)._request("GET", "/pods") or []
    except RunPodError as e:
        raise IntegrationError(e.args[0]) from e
    return f"Connected. {len(pods)} pods on the account."


register(
    Integration(
        key="runpod",
        title="RunPod",
        description="Connect the org's RunPod account.",
        fields=(Field(SECRET_NAME, "API key", "RunPod > Settings > API Keys, with read and write access."),),
        docs="modules/compute",
        test=_test,
    )
)
