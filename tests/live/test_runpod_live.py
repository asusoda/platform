"""The RunPod v2 calls Platform makes, against the live API. Opt in: make ci does not collect tests/live.

    RUNPOD_LIVE_API_KEY=... uv run pytest tests/live/test_runpod_live.py
    RUNPOD_LIVE_API_KEY=... RUNPOD_LIVE_CREATE=1 uv run pytest tests/live/test_runpod_live.py

The first command only reads. RUNPOD_LIVE_CREATE=1 also creates the smallest CPU pod, starts, stops and
restarts it, and deletes it. That costs a few cents.
"""

import os
import time
import uuid

import pytest

from core import hosting
from core.hosting import runpod
from tests.contract import runpod_v2

KEY = os.environ.get("RUNPOD_LIVE_API_KEY", "")
pytestmark = pytest.mark.skipif(not KEY, reason="set RUNPOD_LIVE_API_KEY to run the live RunPod check")
PROVIDER = runpod.RunPodProvider()
WAIT_SECONDS = 300


@pytest.fixture
def client() -> runpod.RunPodClient:
    return runpod.RunPodClient(KEY)


def test_list_pods_reads_the_envelope(client):
    pods = client.list_pods()
    assert isinstance(pods, list)
    for pod in pods:
        runpod_v2.check(pod, "Pod")


def test_the_cpu_catalog_has_a_flavor_for_a_small_app(client):
    flavors = client.cpu_types()
    runpod_v2.check({"cpus": flavors}, "ListCpuTypesResponse")
    picked = runpod.smallest_cpu(flavors, 1024, 2)
    assert picked["vcpuCount"] >= 2 and picked["id"] in {f["id"] for f in flavors}


def _wait(client, pod_id: str, status: str) -> dict:
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        pod = client.get_pod(pod_id)
        if pod is not None and pod.get("status") == status:
            return pod
        time.sleep(5)
    raise AssertionError(f"pod {pod_id} did not reach {status} in {WAIT_SECONDS} seconds")


@pytest.mark.skipif(os.environ.get("RUNPOD_LIVE_CREATE") != "1", reason="set RUNPOD_LIVE_CREATE=1 to create a pod")
def test_create_action_and_delete_the_smallest_cpu_pod(client):
    name = f"live-{uuid.uuid4().hex[:8]}"
    manifest = {"memory": 1024, "cpus": 2, "ports": ["80/http"], "disk": 5, "health": {"port": 80, "path": "/"}}
    PROVIDER.validate(manifest)
    _, _, body = PROVIDER.request(name, "platform", None, manifest, "nginx:1.27-alpine", {}, client)
    runpod_v2.check(body, "CreatePodRequest")
    created = client.create_pod(body)
    pod_id = str(created["id"])
    try:
        runpod_v2.check(created, "Pod")
        found = hosting.find_by_name(PROVIDER, client, body["name"])
        assert found is not None and found["id"] == pod_id
        _wait(client, pod_id, "RUNNING")
        client.stop_pod(pod_id)
        _wait(client, pod_id, "EXITED")
        client.start_pod(pod_id)
        _wait(client, pod_id, "RUNNING")
        client.restart_pod(pod_id)
        _wait(client, pod_id, "RUNNING")
        _, _, patch = PROVIDER.request(name, "platform", pod_id, manifest, "nginx:1.27-alpine", {"A": "1"}, client)
        runpod_v2.check(client.update_pod(pod_id, patch), "Pod")
    finally:
        client.delete_pod(pod_id)
    gone = client.get_pod(pod_id)
    assert gone is None or gone.get("status") == hosting.TERMINATED
