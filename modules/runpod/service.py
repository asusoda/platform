"""Apps on RunPod: manifests, deploys, health checks, rollback. No Flask here.

An officer registers an app's manifest (the pod's hardware, ports, env and health path). The app's
CI then deploys a new image tag with a token that can do nothing else. The first deploy creates the
pod; later deploys change its image, which restarts it. A job polls the health path and marks the
deployment healthy or failed. Each org pays with its own RunPod key, the org secret runpod_api_key.
"""

import datetime
import json
import re
from typing import Any

import jsonschema
import requests

from core import runpod, secrets
from core.logging_config import get_logger
from modules.auth import scopes
from modules.runpod.models import App, AppDeployment

logger = get_logger("runpod")

SECRET_PREFIX = "app_"  # nosec B105 - a secret name prefix, not a value
secrets.declare(runpod.SECRET_NAME, "RunPod API key the org's apps are deployed and billed with")
secrets.declare_prefix(SECRET_PREFIX, "An env value for an app on RunPod, named in its manifest's secret_env")

scopes.declare("apps:read", "List apps on RunPod, their pods and deployments")
scopes.declare("apps:manage", "Register app manifests and roll apps back")
scopes.declare("apps:deploy", "Deploy a new image tag of an app")

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
TAG_PATTERN = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|sha256:[a-f0-9]{64})$")
HEALTH_TIMEOUT = datetime.timedelta(minutes=15)
REDACTED = "(secret)"

_PORT = {"type": "string", "pattern": r"^[0-9]{1,5}/(http|tcp)$"}
MANIFEST_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "image": {"type": "string", "pattern": r"^[a-z0-9][a-z0-9._/-]{0,250}$"},
        "gpu": {
            "type": "object",
            "properties": {"id": {"type": "string", "minLength": 1}, "count": {"type": "integer", "minimum": 1}},
            "required": ["id"],
            "additionalProperties": False,
        },
        "cpu": {
            "type": "object",
            "properties": {"id": {"type": "string", "minLength": 1}, "vcpuCount": {"type": "integer", "minimum": 2}},
            "required": ["id", "vcpuCount"],
            "additionalProperties": False,
        },
        "cloud": {"enum": ["SECURE", "COMMUNITY"]},
        "dataCenterIds": {"type": "array", "items": {"type": "string"}},
        "disk": {"type": "integer", "minimum": 1, "maximum": 2000},
        "ports": {"type": "array", "items": _PORT},
        "args": {"type": "string"},
        "registry": {"type": "string"},
        "env": {"type": "object", "additionalProperties": {"type": "string"}},
        "secret_env": {
            "description": "Pod env var name to org secret name",
            "type": "object",
            "additionalProperties": {"type": "string", "pattern": r"^app_[a-z0-9_]{1,96}$"},
        },
        "mounts": {"type": "object"},
        "health": {
            "type": "object",
            "properties": {
                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                "path": {"type": "string", "pattern": r"^/[^\s]*$"},
            },
            "required": ["port", "path"],
            "additionalProperties": False,
        },
    },
    "required": ["image", "health"],
    "oneOf": [{"required": ["gpu"]}, {"required": ["cpu"]}],
    "additionalProperties": False,
}


class AppError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def client_for(db, org_id: int) -> runpod.RunPodClient:
    key = secrets.get_secret(db, org_id, runpod.SECRET_NAME)
    if not key:
        raise AppError(f"Set the org secret {runpod.SECRET_NAME} to deploy to RunPod", 503)
    return runpod.RunPodClient(key)


def _find(db, org_id: int, name: str) -> App:
    app = db.query(App).filter_by(organization_id=org_id, name=name).first()
    if app is None:
        raise AppError("No app with this name", 404)
    return app


def _manifest(app: App) -> dict:
    return json.loads(str(app.manifest))


def _deployment_dict(d: AppDeployment) -> dict:
    return {
        "id": d.id,
        "tag": d.tag,
        "status": d.status,
        "actor": d.actor,
        "error": d.error,
        "started_at": _iso(d.started_at),
        "finished_at": _iso(d.finished_at),
    }


def _latest(db, app: App) -> AppDeployment | None:
    return db.query(AppDeployment).filter_by(app_id=app.id).order_by(AppDeployment.started_at.desc()).first()


def _app_dict(db, app: App) -> dict:
    latest = _latest(db, app)
    return {
        "name": app.name,
        "manifest": _manifest(app),
        "pod_id": app.pod_id,
        "current_tag": app.current_tag,
        "latest_deployment": _deployment_dict(latest) if latest else None,
        "updated_at": _iso(app.updated_at),
    }


def put_app(db, org_id: int, name: str, manifest: Any) -> dict:
    """Create an app or replace its manifest. Commits."""
    if not NAME_PATTERN.match(name):
        raise AppError("name must be lowercase letters, digits and dashes, up to 63")
    try:
        jsonschema.validate(manifest, MANIFEST_SCHEMA)
    except jsonschema.ValidationError as e:
        raise AppError(f"Invalid manifest: {e.message}") from e
    app = db.query(App).filter_by(organization_id=org_id, name=name).first()
    if app is None:
        app = App(organization_id=org_id, name=name)
        db.add(app)
    app.manifest = json.dumps(manifest, sort_keys=True)
    app.updated_at = _now()
    db.commit()
    return _app_dict(db, app)


def list_apps(db, org_id: int) -> list[dict]:
    return [_app_dict(db, a) for a in db.query(App).filter_by(organization_id=org_id).order_by(App.name).all()]


def get_app(db, org_id: int, name: str) -> dict:
    return _app_dict(db, _find(db, org_id, name))


def delete_app(db, org_id: int, name: str) -> dict:
    """Forget the app. The pod keeps running; terminate it in RunPod. Commits."""
    app = _find(db, org_id, name)
    pod_id = app.pod_id
    db.query(AppDeployment).filter_by(app_id=app.id).delete(synchronize_session=False)
    db.delete(app)
    db.commit()
    return {"deleted": True, "pod_id": pod_id}


def deployments(db, org_id: int, name: str, limit: int = 20) -> list[dict]:
    app = _find(db, org_id, name)
    rows = (
        db.query(AppDeployment)
        .filter_by(app_id=app.id)
        .order_by(AppDeployment.started_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [_deployment_dict(d) for d in rows]


def pod(db, org_id: int, name: str) -> dict | None:
    app = _find(db, org_id, name)
    if not app.pod_id:
        return None
    try:
        return client_for(db, org_id).get_pod(str(app.pod_id))
    except runpod.RunPodError as e:
        raise AppError(e.message, 502) from e


def _env(db, org_id: int, manifest: dict, redact: bool) -> dict[str, str]:
    env = dict(manifest.get("env") or {})
    for var, secret_name in (manifest.get("secret_env") or {}).items():
        if redact:
            env[var] = REDACTED
            continue
        value = secrets.get_secret(db, org_id, secret_name)
        if value is None:
            raise AppError(f"The org secret {secret_name} for {var} is not set", 409)
        env[var] = value
    return env


def _request(db, org_id: int, org_prefix: str, app: App, tag: str, redact: bool) -> tuple[str, str, dict]:
    """The RunPod call a deploy makes: create the pod, or change the existing one."""
    manifest = _manifest(app)
    image = f"{manifest['image']}@{tag}" if tag.startswith("sha256:") else f"{manifest['image']}:{tag}"
    body: dict[str, Any] = {"image": image, "env": _env(db, org_id, manifest, redact)}
    for field in ("disk", "ports", "args", "registry"):
        if field in manifest:
            body[field] = manifest[field]
    if app.pod_id:
        return "PATCH", f"/pods/{app.pod_id}", body
    body["name"] = f"{org_prefix}-{app.name}"
    for field in ("gpu", "cpu", "cloud", "dataCenterIds", "mounts"):
        if field in manifest:
            body[field] = manifest[field]
    return "POST", "/pods", body


def deploy(db, org_id: int, org_prefix: str, name: str, tag: Any, actor: str | None, dry_run: bool = False) -> dict:
    """Point the app's pod at a new image tag, creating the pod on the first deploy. Commits."""
    if not isinstance(tag, str) or not TAG_PATTERN.match(tag):
        raise AppError("tag must be an image tag or a sha256 digest")
    app = _find(db, org_id, name)
    if dry_run:
        method, path, body = _request(db, org_id, org_prefix, app, tag, redact=True)
        return {"dry_run": True, "request": {"method": method, "path": path, "body": body}}

    client = client_for(db, org_id)
    method, _, body = _request(db, org_id, org_prefix, app, tag, redact=False)
    db.query(AppDeployment).filter_by(app_id=app.id, status="deploying").update(
        {"status": "failed", "finished_at": _now(), "error": "Replaced by a later deployment"},
        synchronize_session=False,
    )
    deployment = AppDeployment(app_id=app.id, tag=tag, status="deploying", actor=actor)
    db.add(deployment)
    try:
        if method == "POST":
            created = client.create_pod(body)
            app.pod_id = str(created["id"])
        else:
            client.update_pod(str(app.pod_id), body)
    except (runpod.RunPodError, KeyError, TypeError) as e:
        deployment.status, deployment.finished_at = "failed", _now()
        deployment.error = e.message if isinstance(e, runpod.RunPodError) else "RunPod returned no pod id"
        db.commit()
        raise AppError(f"Deploy failed: {deployment.error}", 502) from e
    app.current_tag, app.updated_at = tag, _now()
    db.commit()
    logger.info("deploy started app=%s tag=%s pod=%s", app.name, tag, app.pod_id)
    return {"deployment": _deployment_dict(deployment), "pod_id": app.pod_id}


def rollback(db, org_id: int, org_prefix: str, name: str, actor: str | None, dry_run: bool = False) -> dict:
    """Deploy the newest healthy tag other than the current one."""
    app = _find(db, org_id, name)
    previous = (
        db.query(AppDeployment)
        .filter(AppDeployment.app_id == app.id, AppDeployment.status == "healthy", AppDeployment.tag != app.current_tag)
        .order_by(AppDeployment.started_at.desc())
        .first()
    )
    if previous is None:
        raise AppError("No earlier healthy deployment to roll back to", 409)
    return deploy(db, org_id, org_prefix, name, str(previous.tag), actor, dry_run)


def _healthy(url: str) -> bool:
    try:
        return requests.get(url, timeout=10).status_code < 400
    except requests.RequestException:
        return False


def check_deployments(db, now: datetime.datetime | None = None) -> dict:
    """Mark running deployments healthy when their health path answers, failed after HEALTH_TIMEOUT. Commits."""
    now = now or _now()
    counts = {"healthy": 0, "failed": 0, "waiting": 0}
    running = db.query(AppDeployment, App).join(App, App.id == AppDeployment.app_id)
    for deployment, app in running.filter(AppDeployment.status == "deploying").all():
        health = _manifest(app)["health"]
        if app.pod_id and _healthy(runpod.proxy_url(str(app.pod_id), health["port"], health["path"])):
            deployment.status, deployment.finished_at = "healthy", now
            counts["healthy"] += 1
        elif deployment.started_at <= now - HEALTH_TIMEOUT:
            deployment.status, deployment.finished_at = "failed", now
            deployment.error = "The health path did not answer in time"
            counts["failed"] += 1
        else:
            counts["waiting"] += 1
    db.commit()
    return counts
