"""RunPodClient calls and RunPodProvider bodies against the RunPod v2 spec, with a fake requests.request."""

import json

import pytest
import requests

from core import hosting
from core.hosting import runpod
from tests.contract import runpod_v2

BASE = "https://api.runpod.io/v2"


class Answer:
    def __init__(self, body, status=200):
        self.status_code = status
        self._body = body
        self.content = b"" if body is None else json.dumps(body).encode()
        self.text = self.content.decode()

    def json(self):
        return self._body


@pytest.fixture
def seen(monkeypatch):
    """Each request as (method, url, json body); answers come from the answers list, else the example pod."""
    calls: list[tuple] = []
    answers: list[Answer] = []

    def fake(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        assert kwargs["headers"]["Authorization"] == "Bearer key"
        return answers.pop(0) if answers else Answer(runpod_v2.load("get_pod"))

    monkeypatch.setattr(requests, "request", fake)
    return calls, answers


def test_gpu_types_reads_pod_stock_for_one_cloud(seen):
    calls, answers = seen
    answers.append(Answer({"gpus": [{"id": "NVIDIA L4", "availability": "HIGH"}]}))
    assert runpod.RunPodClient("key").gpu_types("SECURE") == [{"id": "NVIDIA L4", "availability": "HIGH"}]
    assert calls == [("GET", f"{BASE}/catalog/gpus?include=AVAILABILITY&product=POD&count=1&cloud=SECURE", None)]


def test_cpu_types_reads_the_pod_catalog(seen):
    calls, answers = seen
    answers.append(Answer(runpod_v2.load("cpu_types")))
    runpod_v2.check(runpod_v2.load("cpu_types"), "ListCpuTypesResponse")
    assert [c["id"] for c in runpod.RunPodClient("key").cpu_types()] == ["cpu3c-2-4"]
    assert calls == [("GET", f"{BASE}/catalog/cpus?product=POD", None)]


def test_list_pods_reads_the_envelope_and_every_page(seen):
    calls, answers = seen
    first = runpod_v2.load("list_pods")
    runpod_v2.check(first, "ListPodsResponse")
    first["pagination"] = {"nextCursor": "c/2", "hasNextPage": True}
    second = {"pods": [runpod_v2.pod(id="second")], "pagination": {"nextCursor": None, "hasNextPage": False}}
    answers.extend([Answer(first), Answer(second)])
    pods = runpod.RunPodClient("key").list_pods()
    assert [p["id"] for p in pods] == ["7h9k2m4n6p", "second"]
    assert [c[1] for c in calls] == [f"{BASE}/pods", f"{BASE}/pods?cursor=c%2F2"]


def test_start_stop_and_restart_post_an_action(seen):
    calls, _ = seen
    client = runpod.RunPodClient("key")
    client.start_pod("abc")
    client.stop_pod("abc")
    client.restart_pod("abc")
    assert calls == [("POST", f"{BASE}/pods/abc/action", {"action": a}) for a in ("start", "stop", "restart")]
    runpod_v2.check(runpod_v2.load("pod_action_request"), "PodActionRequest")
    for _, _, body in calls:
        runpod_v2.check(body, "PodActionRequest")


def test_create_get_update_and_delete_paths(seen):
    calls, answers = seen
    client = runpod.RunPodClient("key")
    runpod_v2.check(runpod_v2.load("create_pod_request"), "CreatePodRequest")
    runpod_v2.check(runpod_v2.load("create_pod_response"), "Pod")
    runpod_v2.check(runpod_v2.load("update_pod_response"), "Pod")
    answers.append(Answer(runpod_v2.load("create_pod_response"), 201))
    assert client.create_pod(runpod_v2.load("create_pod_request"))["status"] == "PROVISIONING"
    assert (client.get_pod("7h9k2m4n6p") or {})["id"] == "7h9k2m4n6p"
    client.update_pod("7h9k2m4n6p", {"image": "x:1"})
    answers.append(Answer(None, 204))
    assert client.delete_pod("7h9k2m4n6p") is None
    answers.append(Answer({"error": "pod not found"}, 404))
    assert client.get_pod("gone") is None
    assert [(m, u) for m, u, _ in calls] == [
        ("POST", f"{BASE}/pods"),
        ("GET", f"{BASE}/pods/7h9k2m4n6p"),
        ("PATCH", f"{BASE}/pods/7h9k2m4n6p"),
        ("DELETE", f"{BASE}/pods/7h9k2m4n6p"),
        ("GET", f"{BASE}/pods/gone"),
    ]


def test_the_integration_test_counts_the_pods(seen, monkeypatch):
    _, answers = seen
    answers.append(Answer(runpod_v2.load("list_pods")))
    monkeypatch.setattr(runpod.secrets, "get_secret", lambda db, org_id, name: "key")
    assert runpod._test(None, 1) == "Connected. 1 pods on the account."


# The provider reads the v2 pod and builds v2 bodies

PROVIDER = runpod.RunPodProvider()
HEALTH = {"port": 8080, "path": "/health"}


def test_the_provider_reads_the_v2_pod():
    pod = runpod_v2.load("get_pod")
    runpod_v2.check(pod, "Pod")
    assert PROVIDER.status(pod) == "RUNNING" and PROVIDER.status(None) == "GONE"
    assert PROVIDER.pod_name(pod) == "pytorch-training"
    assert PROVIDER.ssh_address(pod) == ("195.26.233.3", 34446)
    assert PROVIDER.machine(pod) == {"gpuTypeId": "NVIDIA GeForce RTX 4090", "dataCenterId": "US-KS-2"}
    # Without ssh.direct the runtime port with private 22 gives the address
    assert PROVIDER.ssh_address(pod | {"ssh": {"proxy": None, "direct": None}}) == ("195.26.233.3", 34446)
    assert PROVIDER.ssh_address(runpod_v2.load("create_pod_response")) is None


class Catalog(runpod.RunPodClient):
    """A client whose catalog is the spec's example, and that makes no request."""

    def __init__(self):
        super().__init__("key")

    def cpu_types(self):
        return runpod_v2.load("cpu_types")["cpus"]


@pytest.mark.parametrize(
    "manifest",
    [
        {"image": "ghcr.io/a/b", "gpu": {"id": "NVIDIA L4", "count": 1}, "ports": ["8080/http"], "health": HEALTH},
        {"image": "ghcr.io/a/b", "cpu": {"id": "cpu3c", "vcpuCount": 4}, "disk": 20, "health": HEALTH},
        {"image": "ghcr.io/a/b", "memory": 4096, "cpus": 1, "env": {"A": "1"}, "health": HEALTH},
        {
            "image": "ghcr.io/a/b",
            "gpu": {"id": "NVIDIA L4"},
            "mounts": {"persistent": {"size": 20, "path": "/workspace"}},
            "cloud": "SECURE",
            "dataCenterIds": ["US-KS-2"],
            "health": HEALTH,
        },
    ],
)
def test_create_and_update_bodies_match_the_spec(manifest):
    PROVIDER.validate(manifest)
    method, path, body = PROVIDER.request("bot", "ais", None, manifest, "ghcr.io/a/b:v1", {"A": "1"}, Catalog())
    assert (method, path, body["name"]) == ("POST", "/pods", "ais-bot")
    runpod_v2.check(body, "CreatePodRequest")
    method, path, body = PROVIDER.request("bot", "ais", "abc", manifest, "ghcr.io/a/b:v2", {}, Catalog())
    assert (method, path) == ("PATCH", "/pods/abc") and not {"gpu", "cpu", "mounts", "name"} & set(body)
    runpod_v2.check(body, "UpdatePodRequest")


def test_memory_and_cpus_pick_a_flavor_from_the_catalog():
    _, _, body = PROVIDER.request("bot", "ais", None, {"memory": 6000, "cpus": 3}, "i:1", {}, Catalog())
    # 4 vCPUs of 2.5 GB give 10 GB: the power of two at or above 3 vCPUs and 6000 MB
    assert body["cpu"] == {"id": "cpu3c-2-4", "vcpuCount": 4}
    with pytest.raises(hosting.HostingError, match="Connect RunPod"):
        PROVIDER.request("bot", "ais", None, {"memory": 6000}, "i:1", {}, None)


def test_smallest_cpu_picks_the_cheapest_flavor_that_fits():
    flavors = [
        {"id": "a", "vcpu": {"min": 2, "max": 32}, "ramGbPerVcpu": 2, "price": {"securePerVcpu": 0.02}},
        {"id": "b", "vcpu": {"min": 4, "max": 8}, "ramGbPerVcpu": 8, "price": {"securePerVcpu": 0.05}},
    ]
    assert runpod.smallest_cpu(flavors, 0, 0) == {"id": "a", "vcpuCount": 2}
    assert runpod.smallest_cpu(flavors, 8 * 1024, 3) == {"id": "a", "vcpuCount": 4}
    # 16 vCPUs of a cost more than 4 of b
    assert runpod.smallest_cpu(flavors, 32 * 1024, 0) == {"id": "b", "vcpuCount": 4}
    assert runpod.smallest_cpu(flavors, 64 * 1024, 0) == {"id": "b", "vcpuCount": 8}
    with pytest.raises(runpod.RunPodError) as refused:
        runpod.smallest_cpu(flavors, 128 * 1024, 0)
    assert refused.value.status == 400


@pytest.mark.parametrize(
    ("manifest", "error"),
    [
        ({"gpu": {"id": "x"}, "cpu": {"id": "y", "vcpuCount": 2}}, "not both"),
        ({"health": {"port": 1, "tcp": True}}, "health path"),
        ({"command": ["x"]}, "This server"),
        ({"cpu": {"id": "y", "vcpuCount": 2}, "mounts": {"persistent": {"size": 20, "path": "/w"}}}, "GPU pod"),
        ({"gpu": {"id": "x"}, "mounts": {"persistent": {"size": 5, "path": "/w"}}}, "10 GB"),
    ],
)
def test_validate_refuses_what_runpod_refuses(manifest, error):
    with pytest.raises(hosting.HostingError, match=error):
        PROVIDER.validate({"image": "i", "health": HEALTH} | manifest)
