"""Apps on RunPod: manifests, deploys, health checks, rollback. No Flask here.

An officer registers an app's manifest (the pod's hardware, ports, env and health path), or the
app's repo, whose platform.app.yaml is then read at the deployed git ref. The app's CI deploys a
new image tag with a token that can do nothing else. The first deploy creates the
pod; later deploys change its image, which restarts it. A job polls the health path and marks the
deployment healthy or failed. Each org pays with its own RunPod key, the org secret runpod_api_key.
"""

import datetime
import json
import re
from typing import Any
from urllib.parse import quote

import jsonschema
import requests
import yaml

from core import secrets
from core.errors import ServiceError
from core.integrations import runpod
from core.log import get_logger
from core.time import iso, utcnow
from modules.auth import scopes
from modules.runpod.models import App, AppDeployment

logger = get_logger("runpod")

SECRET_PREFIX = "app_"  # nosec B105 - a secret name prefix, not a value
secrets.declare(runpod.SECRET_NAME, "RunPod API key the org's apps are deployed and billed with")
GITHUB_SECRET = "github_token"  # nosec B105 - a secret name, not a value
secrets.declare(GITHUB_SECRET, "GitHub token that can read the contents of the org's private app repos")
secrets.declare_prefix(SECRET_PREFIX, "An env value for an app on RunPod, named in its manifest's secret_env")

scopes.declare("apps:read", "List apps on RunPod, their pods and deployments")
scopes.declare("apps:manage", "Register app manifests and roll apps back")
scopes.declare("apps:deploy", "Deploy a new image tag of an app")

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
TAG_PATTERN = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|sha256:[a-f0-9]{64})$")
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
PATH_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}$")
REF_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,99}$")
DEFAULT_MANIFEST_PATH = "platform.app.yaml"
MAX_MANIFEST_BYTES = 100_000
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


class AppError(ServiceError, ValueError):
    pass


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


def _validated(manifest: Any) -> dict:
    try:
        jsonschema.validate(manifest, MANIFEST_SCHEMA)
    except jsonschema.ValidationError as e:
        raise AppError(f"Invalid manifest: {e.message}") from e
    return manifest


def _safe_path(value: str, pattern: re.Pattern, name: str) -> str:
    if not isinstance(value, str) or not pattern.match(value) or ".." in value:
        raise AppError(f"{name} is not valid")
    return value


def fetch_manifest(db, org_id: int, repo: str, path: str, ref: str | None) -> dict:
    """The manifest file in a GitHub repo at ref (the default branch when None), validated."""
    url = f"https://api.github.com/repos/{repo}/contents/{quote(path)}"
    headers = {"Accept": "application/vnd.github.raw+json", "User-Agent": "platform-runpod"}
    token = secrets.get_secret(db, org_id, GITHUB_SECRET)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(url, params={"ref": ref} if ref else {}, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise AppError("GitHub could not be reached", 502) from e
    where = f"{repo} at {ref or 'its default branch'}"
    if response.status_code == 404:
        raise AppError(f"{path} was not found in {where}; private repos need the org secret {GITHUB_SECRET}", 422)
    if response.status_code != 200:
        raise AppError(f"GitHub answered {response.status_code} for {path} in {where}", 502)
    if len(response.content) > MAX_MANIFEST_BYTES:
        raise AppError(f"{path} is larger than {MAX_MANIFEST_BYTES} bytes", 422)
    try:
        manifest = yaml.safe_load(response.text)
    except yaml.YAMLError as e:
        raise AppError(f"{path} in {where} is not valid YAML", 422) from e
    try:
        return _validated(manifest)
    except AppError as e:
        raise AppError(f"{path} in {where}: {e.message}", 422) from e


def _deployment_dict(d: AppDeployment) -> dict:
    return {
        "id": d.id,
        "tag": d.tag,
        "status": d.status,
        "actor": d.actor,
        "error": d.error,
        "manifest_ref": d.manifest_ref,
        "started_at": iso(d.started_at),
        "finished_at": iso(d.finished_at),
    }


def _latest(db, app: App) -> AppDeployment | None:
    return db.query(AppDeployment).filter_by(app_id=app.id).order_by(AppDeployment.started_at.desc()).first()


def _app_dict(db, app: App) -> dict:
    latest = _latest(db, app)
    return {
        "name": app.name,
        "manifest": _manifest(app),
        "repo": app.repo,
        "manifest_path": app.manifest_path,
        "pod_id": app.pod_id,
        "current_tag": app.current_tag,
        "latest_deployment": _deployment_dict(latest) if latest else None,
        "updated_at": iso(app.updated_at),
    }


def put_app(db, org_id: int, name: str, manifest: Any = None, repo: Any = None, manifest_path: Any = None) -> dict:
    """Create an app or replace its manifest. Takes a manifest, or a repo whose manifest file is read
    now from the default branch and again at each deploy's ref. Commits."""
    if not NAME_PATTERN.match(name):
        raise AppError("name must be lowercase letters, digits and dashes, up to 63")
    if (manifest is None) == (repo is None):
        raise AppError("Send either manifest or repo")
    path = None
    if repo is not None:
        repo = _safe_path(repo, REPO_PATTERN, "repo (owner/name)")
        path = _safe_path(manifest_path or DEFAULT_MANIFEST_PATH, PATH_PATTERN, "manifest_path")
        manifest = fetch_manifest(db, org_id, repo, path, None)
    else:
        _validated(manifest)
    app = db.query(App).filter_by(organization_id=org_id, name=name).first()
    if app is None:
        app = App(organization_id=org_id, name=name)
        db.add(app)
    app.repo, app.manifest_path = repo, path
    app.manifest = json.dumps(manifest, sort_keys=True)
    app.updated_at = utcnow()
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


def _request(
    db, org_id: int, org_prefix: str, app: App, manifest: dict, tag: str, redact: bool
) -> tuple[str, str, dict]:
    """The RunPod call a deploy makes: create the pod, or change the existing one."""
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


def deploy(
    db,
    org_id: int,
    org_prefix: str,
    name: str,
    tag: Any,
    actor: str | None,
    dry_run: bool = False,
    ref: Any = None,
    manifest: dict | None = None,
) -> dict:
    """Point the app's pod at a new image tag, creating the pod on the first deploy. Commits.

    An app with a repo reads its manifest file at ref first. manifest, from a rollback, skips that.
    """
    if not isinstance(tag, str) or not TAG_PATTERN.match(tag):
        raise AppError("tag must be an image tag or a sha256 digest")
    app = _find(db, org_id, name)
    manifest_ref = None
    if manifest is None and app.repo:
        manifest_ref = _safe_path(ref, REF_PATTERN, "ref") if ref is not None else None
        manifest = fetch_manifest(db, org_id, str(app.repo), str(app.manifest_path), manifest_ref)
    elif ref is not None and manifest is None:
        raise AppError("ref applies only to apps registered with a repo")
    manifest = manifest if manifest is not None else _manifest(app)
    if dry_run:
        method, path, body = _request(db, org_id, org_prefix, app, manifest, tag, redact=True)
        return {"dry_run": True, "manifest": manifest, "request": {"method": method, "path": path, "body": body}}

    client = client_for(db, org_id)
    method, _, body = _request(db, org_id, org_prefix, app, manifest, tag, redact=False)
    db.query(AppDeployment).filter_by(app_id=app.id, status="deploying").update(
        {"status": "failed", "finished_at": utcnow(), "error": "Replaced by a later deployment"},
        synchronize_session=False,
    )
    stored = json.dumps(manifest, sort_keys=True)
    deployment = AppDeployment(
        app_id=app.id, tag=tag, status="deploying", actor=actor, manifest=stored, manifest_ref=manifest_ref
    )
    app.manifest = stored
    db.add(deployment)
    try:
        if method == "POST":
            created = client.create_pod(body)
            app.pod_id = str(created["id"])
        else:
            client.update_pod(str(app.pod_id), body)
    except (runpod.RunPodError, KeyError, TypeError) as e:
        deployment.status, deployment.finished_at = "failed", utcnow()
        deployment.error = e.message if isinstance(e, runpod.RunPodError) else "RunPod returned no pod id"
        db.commit()
        raise AppError(f"Deploy failed: {deployment.error}", 502) from e
    app.current_tag, app.updated_at = tag, utcnow()
    db.commit()
    logger.info("deploy started app=%s tag=%s pod=%s", app.name, tag, app.pod_id)
    return {"deployment": _deployment_dict(deployment), "pod_id": app.pod_id}


def rollback(db, org_id: int, org_prefix: str, name: str, actor: str | None, dry_run: bool = False) -> dict:
    """Deploy the newest healthy tag other than the current one, with the manifest it ran with."""
    app = _find(db, org_id, name)
    previous = (
        db.query(AppDeployment)
        .filter(AppDeployment.app_id == app.id, AppDeployment.status == "healthy", AppDeployment.tag != app.current_tag)
        .order_by(AppDeployment.started_at.desc())
        .first()
    )
    if previous is None:
        raise AppError("No earlier healthy deployment to roll back to", 409)
    manifest = json.loads(str(previous.manifest)) if previous.manifest else None
    return deploy(db, org_id, org_prefix, name, str(previous.tag), actor, dry_run, manifest=manifest)


def _healthy(url: str) -> bool:
    try:
        return requests.get(url, timeout=10).status_code < 400
    except requests.RequestException:
        return False


def check_deployments(db, now: datetime.datetime | None = None) -> dict:
    """Mark running deployments healthy when their health path answers, failed after HEALTH_TIMEOUT. Commits."""
    now = now or utcnow()
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
