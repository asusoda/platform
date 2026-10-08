"""Pods on an org's RunPod account: officers manage them, members connect with short-lived certificates."""

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization import load_ssh_public_identity

from tests.contract.conftest import MEMBER_DISCORD_ID


class FakeRunPod:
    def __init__(self):
        self.pods: dict[str, dict] = {}
        self.calls: list[tuple] = []

    def create_pod(self, body):
        pod_id = f"pod{len(self.pods) + 1}"
        self.calls.append(("create", body))
        self.pods[pod_id] = {
            "id": pod_id,
            "desiredStatus": "RUNNING",
            "publicIp": "203.0.113.5",
            "portMappings": {"22": 40022},
        }
        return self.pods[pod_id]

    def get_pod(self, pod_id):
        return self.pods.get(pod_id)

    def start_pod(self, pod_id):
        self.calls.append(("start", pod_id))
        self.pods[pod_id]["desiredStatus"] = "RUNNING"

    def stop_pod(self, pod_id):
        self.calls.append(("stop", pod_id))
        self.pods[pod_id]["desiredStatus"] = "EXITED"

    def delete_pod(self, pod_id):
        self.calls.append(("delete", pod_id))
        self.pods.pop(pod_id)


@pytest.fixture
def runpod(app, monkeypatch):
    from modules.compute import service
    from modules.compute.models import ComputeKey, ComputePod
    from shared import db_connect

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    fake = FakeRunPod()
    monkeypatch.setattr(service, "_client", lambda db, org_id: fake)
    yield fake
    db = db_connect.SessionLocal()
    db.query(ComputePod).delete()
    db.query(ComputeKey).delete()
    db.commit()
    db.close()


def _user_key():
    from modules.compute import ssh

    return ssh.generate_keypair("alice@laptop")[0]


def _create(client, headers, **body):
    return client.post("/api/compute/soda/pods", json={"name": "workshop", **body}, headers=headers)


def test_officer_creates_and_lists_a_pod(client, officer_headers, runpod):
    response = _create(client, officer_headers, gpu_type_id="NVIDIA A40", env={"HF_HOME": "/workspace/hf"})
    assert response.status_code == 201
    assert response.get_json()["pod"]["status"] == "RUNNING"
    _, body = runpod.calls[0]
    assert body["computeType"] == "GPU" and body["gpuTypeIds"] == ["NVIDIA A40"]
    assert body["imageName"] == "theaisocietyasu/godfather-base:latest" and body["ports"] == ["22/tcp"]
    assert body["env"]["HF_HOME"] == "/workspace/hf"
    assert body["env"]["GODFATHER_SSH_CA_PUBLIC_KEY"].startswith("ssh-ed25519 ")
    assert "PRIVATE" not in str(body)

    pods = client.get("/api/compute/soda/pods", headers=officer_headers).get_json()["pods"]
    assert [(p["id"], p["name"], p["status"]) for p in pods] == [("pod1", "workshop", "RUNNING")]


def test_cpu_pods_and_bad_requests(client, officer_headers, runpod):
    assert _create(client, officer_headers, use_cpu_only=True).status_code == 201
    _, body = runpod.calls[0]
    assert body["computeType"] == "CPU" and body["cpuFlavorIds"] == ["cpu3c"] and "gpuTypeIds" not in body
    for bad in (
        {"env": {"GODFATHER_SETUP": "false"}},
        {"volume_in_gb": -1},
        {"cloud_type": "MOON"},
        {"allowed_users": ["not-an-id"]},
    ):
        assert _create(client, officer_headers, **bad).status_code == 400


def test_member_sees_and_connects_to_shared_running_pods(client, member_client, officer_headers, runpod, monkeypatch):
    from modules.compute import api

    monkeypatch.setattr(api, "_is_officer", lambda org, discord_id: False)
    _create(client, officer_headers)
    assert member_client.get("/api/compute/soda/me/pods").get_json() == {"pods": []}
    key = _user_key()
    denied = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": key})
    assert denied.status_code == 403

    shared = client.put(
        "/api/compute/soda/pods/pod1", json={"allowed_users": [MEMBER_DISCORD_ID]}, headers=officer_headers
    )
    assert shared.get_json()["pod"]["allowed_users"] == [MEMBER_DISCORD_ID]
    assert [p["id"] for p in member_client.get("/api/compute/soda/me/pods").get_json()["pods"]] == ["pod1"]

    info = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": key}).get_json()["ssh_info"]
    assert (info["host"], info["port"], info["username"], info["is_admin"]) == ("203.0.113.5", 40022, "root", False)
    cert = load_ssh_public_identity(info["certificate"].encode())
    assert cert.valid_principals == [b"gf-pod1"]
    assert cert.critical_options[b"force-command"].startswith(b"/usr/local/bin/godfather-login ")
    assert member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": "nope"}).status_code == 400

    client.post("/api/compute/soda/pods/pod1/action", json={"action": "stop"}, headers=officer_headers)
    assert member_client.get("/api/compute/soda/me/pods").get_json() == {"pods": []}
    stopped = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": key})
    assert stopped.status_code == 409


def test_officers_get_root_certificates(client, member_client, officer_headers, runpod):
    _create(client, officer_headers)
    info = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": _user_key()}).get_json()
    cert = load_ssh_public_identity(info["ssh_info"]["certificate"].encode())
    assert info["ssh_info"]["is_admin"] is True and cert.critical_options == {}


def test_actions_and_terminate(client, officer_headers, runpod):
    _create(client, officer_headers)
    for action in ("stop", "start", "restart"):
        assert (
            client.post(
                "/api/compute/soda/pods/pod1/action", json={"action": action}, headers=officer_headers
            ).status_code
            == 200
        )
    assert runpod.calls[1:] == [("stop", "pod1"), ("start", "pod1"), ("stop", "pod1"), ("start", "pod1")]
    assert (
        client.post(
            "/api/compute/soda/pods/pod1/action", json={"action": "explode"}, headers=officer_headers
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/compute/soda/pods/pod1/action", json={"action": "terminate"}, headers=officer_headers
        ).status_code
        == 200
    )
    assert client.get("/api/compute/soda/pods", headers=officer_headers).get_json() == {"pods": []}
    assert client.get("/api/compute/soda/pods/pod1", headers=officer_headers).status_code == 404


def test_keys_are_stored_encrypted_and_reused(client, officer_headers, runpod):
    from modules.compute.models import ComputeKey
    from shared import db_connect

    _create(client, officer_headers)
    _create(client, officer_headers, name="second")
    first_ca = runpod.calls[0][1]["env"]["GODFATHER_SSH_CA_PUBLIC_KEY"]
    assert runpod.calls[1][1]["env"]["GODFATHER_SSH_CA_PUBLIC_KEY"] == first_ca
    db = db_connect.SessionLocal()
    rows = db.query(ComputeKey).all()
    db.close()
    assert sorted(r.kind for r in rows) == ["backend", "user_ca"]
    assert all("PRIVATE KEY" not in r.private_key for r in rows)


def test_without_a_runpod_key_the_org_is_told(client, officer_headers, app, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    response = _create(client, officer_headers)
    assert response.status_code == 400 and "runpod_api_key" in response.get_json()["error"]


def test_turning_compute_off_hides_the_routes(client, officer_headers, runpod, restore_soda_config):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    soda_id = next(o["id"] for o in orgs if o["prefix"] == "soda")
    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"compute": False}}, headers=officer_headers)
    assert client.get("/api/compute/soda/pods", headers=officer_headers).status_code == 404
