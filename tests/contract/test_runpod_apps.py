"""Apps on RunPod: manifests, deploys with a narrow token, health checks, rollback."""

import datetime
import uuid

import pytest
from cryptography.fernet import Fernet

from core import runpod
from modules.runpod import service
from shared import db_connect


class FakeRunPod:
    def __init__(self):
        self.calls = []
        self.fail = False

    def create_pod(self, body):
        self.calls.append(("POST", None, body))
        if self.fail:
            raise runpod.RunPodError("RunPod answered 500", 500)
        return {"id": "pod123"}

    def update_pod(self, pod_id, body):
        self.calls.append(("PATCH", pod_id, body))
        if self.fail:
            raise runpod.RunPodError("RunPod answered 500", 500)
        return {"id": pod_id}

    def get_pod(self, pod_id):
        return {"id": pod_id, "desiredStatus": "RUNNING"}


@pytest.fixture
def fake(monkeypatch):
    client = FakeRunPod()
    monkeypatch.setattr(service, "client_for", lambda db, org_id: client)
    return client


@pytest.fixture
def healthy(monkeypatch):
    state = {"up": True, "urls": []}

    def check(url):
        state["urls"].append(url)
        return state["up"]

    monkeypatch.setattr(service, "_healthy", check)
    return state


def _issue(prefix, *scopes):
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(db, organization_id=org_id, name="ci", kind="app", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


@pytest.fixture
def manager(app):
    return _issue("ais", "apps:read", "apps:manage")


@pytest.fixture
def deployer(app):
    return _issue("ais", "apps:deploy")


MANIFEST = {
    "image": "ghcr.io/ashworks1706/sparky",
    "gpu": {"id": "NVIDIA RTX A5000", "count": 1},
    "cloud": "SECURE",
    "disk": 50,
    "ports": ["8080/http"],
    "env": {"SPARKY_MODE": "prod"},
    "health": {"port": 8080, "path": "/health"},
}


def _name():
    return "app-" + uuid.uuid4().hex[:8]


def _register(client, manager, manifest=None):
    name = _name()
    response = client.put(f"/api/apps/{name}", json={"manifest": manifest or MANIFEST}, headers=manager)
    assert response.status_code == 200, response.get_json()
    return name


def _check():
    db = db_connect.SessionLocal()
    try:
        return service.check_deployments(db)
    finally:
        db.close()


def test_first_deploy_creates_pod_then_updates_image(client, manager, deployer, fake, healthy):
    name = _register(client, manager)
    first = client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer)
    assert first.status_code == 202, first.get_json()
    method, _, body = fake.calls[-1]
    assert method == "POST" and body["image"] == "ghcr.io/ashworks1706/sparky:v1"
    assert body["name"] == f"ais-{name}" and body["gpu"]["id"] == "NVIDIA RTX A5000"
    assert body["env"] == {"SPARKY_MODE": "prod"}

    assert _check()["healthy"] >= 1
    assert "https://pod123-8080.proxy.runpod.net/health" in healthy["urls"]

    digest = "sha256:" + "a" * 64
    client.post(f"/api/apps/{name}/deploy", json={"tag": digest}, headers=deployer)
    method, pod_id, body = fake.calls[-1]
    assert (method, pod_id) == ("PATCH", "pod123")
    assert body["image"] == f"ghcr.io/ashworks1706/sparky@{digest}"
    assert "gpu" not in body and "name" not in body

    info = client.get(f"/api/apps/{name}", headers=manager).get_json()
    assert info["current_tag"] == digest and info["pod_id"] == "pod123"


def test_deploy_token_can_only_deploy(client, manager, deployer, fake):
    name = _register(client, manager)
    assert client.put(f"/api/apps/{name}", json={"manifest": MANIFEST}, headers=deployer).status_code == 403
    assert client.get(f"/api/apps/{name}", headers=deployer).status_code == 403
    assert client.post(f"/api/apps/{name}/rollback", headers=deployer).status_code == 403
    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=manager).status_code == 403
    soda = _issue("soda", "apps:deploy")
    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=soda).status_code == 404


def test_secret_env_comes_from_org_secrets_and_dry_run_redacts(client, manager, deployer, fake, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    manifest = {**MANIFEST, "secret_env": {"DISCORD_TOKEN": "app_sparky_discord_token"}}
    name = _register(client, manager, manifest)

    dry = client.post(f"/api/apps/{name}/deploy", json={"tag": "v1", "dry_run": True}, headers=deployer)
    assert dry.status_code == 200
    assert dry.get_json()["request"]["body"]["env"]["DISCORD_TOKEN"] == service.REDACTED
    assert fake.calls == []

    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer).status_code == 409

    from core import secrets
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix="ais").scalar()
        secrets.set_secret(db, org_id, "app_sparky_discord_token", "real-token")
    finally:
        db.close()
    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer).status_code == 202
    assert fake.calls[-1][2]["env"]["DISCORD_TOKEN"] == "real-token"


def test_failed_health_and_rollback(client, manager, deployer, fake, healthy):
    name = _register(client, manager)
    client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer)
    _check()
    healthy["up"] = False
    client.post(f"/api/apps/{name}/deploy", json={"tag": "v2"}, headers=deployer)
    later = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + service.HEALTH_TIMEOUT
    db = db_connect.SessionLocal()
    try:
        service.check_deployments(db, now=later)
    finally:
        db.close()

    history = client.get(f"/api/apps/{name}/deployments", headers=manager).get_json()["deployments"]
    assert [(d["tag"], d["status"]) for d in history] == [("v2", "failed"), ("v1", "healthy")]

    back = client.post(f"/api/apps/{name}/rollback", headers=manager)
    assert back.status_code == 202, back.get_json()
    assert fake.calls[-1][2]["image"].endswith(":v1")


def test_newer_deploy_replaces_a_running_one(client, manager, deployer, fake, healthy):
    name = _register(client, manager)
    healthy["up"] = False
    client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer)
    client.post(f"/api/apps/{name}/deploy", json={"tag": "v2"}, headers=deployer)
    history = client.get(f"/api/apps/{name}/deployments", headers=manager).get_json()["deployments"]
    assert [(d["tag"], d["status"]) for d in history] == [("v2", "deploying"), ("v1", "failed")]


def test_runpod_failure_is_recorded(client, manager, deployer, fake):
    name = _register(client, manager)
    fake.fail = True
    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer).status_code == 502
    history = client.get(f"/api/apps/{name}/deployments", headers=manager).get_json()["deployments"]
    assert history[0]["status"] == "failed" and "500" in history[0]["error"]
    assert client.get(f"/api/apps/{name}", headers=manager).get_json()["pod_id"] is None


@pytest.mark.parametrize(
    "manifest",
    [
        {k: v for k, v in MANIFEST.items() if k != "health"},
        {k: v for k, v in MANIFEST.items() if k != "gpu"},
        {**MANIFEST, "cpu": {"id": "cpu5c", "vcpuCount": 4}},
        {**MANIFEST, "image": "ghcr.io/x/y:latest"},
        {**MANIFEST, "ports": ["8080"]},
        {**MANIFEST, "unknown": 1},
    ],
)
def test_rejects_bad_manifests(client, manager, manifest):
    assert client.put(f"/api/apps/{_name()}", json={"manifest": manifest}, headers=manager).status_code == 400


def test_rejects_bad_tags_and_names(client, manager, deployer, fake):
    name = _register(client, manager)
    for tag in ("", "v1 v2", "../x", None, "-x"):
        assert client.post(f"/api/apps/{name}/deploy", json={"tag": tag}, headers=deployer).status_code == 400
    assert client.put("/api/apps/Bad_Name", json={"manifest": MANIFEST}, headers=manager).status_code == 400


def test_no_runpod_key(client, manager, deployer):
    name = _register(client, manager)
    response = client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer)
    assert response.status_code == 503


def test_list_tool_and_delete(client, manager, fake):
    name = _register(client, manager)
    tools = client.post("/api/tools/apps.list", json={}, headers=manager).get_json()["result"]["apps"]
    assert name in [a["name"] for a in tools] and "manifest" not in tools[0]
    assert client.delete(f"/api/apps/{name}", headers=manager).get_json()["deleted"] is True
    assert client.get(f"/api/apps/{name}", headers=manager).status_code == 404


def test_app_secrets_need_the_prefix(monkeypatch):
    from core import secrets

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    db = db_connect.SessionLocal()
    try:
        with pytest.raises(secrets.SecretsError):
            secrets.set_secret(db, 1, "anything_else", "x")
        with pytest.raises(secrets.SecretsError):
            secrets.set_secret(db, 1, "app_", "x")
        secrets.set_secret(db, 1, "app_listed", "x")
        listed = {s["name"]: s for s in secrets.list_secrets(db, 1)}
        assert listed["app_listed"]["set"] is True and listed[runpod.SECRET_NAME]["set"] is False
    finally:
        secrets.delete_secret(db, 1, "app_listed")
        db.close()
