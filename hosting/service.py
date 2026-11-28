"""Apps on a hosting provider: register, list, delete, start, stop and read logs. No Flask here.

An officer registers an app's manifest (manifest.py), or the app's repo, whose platform.app.yaml is then read
at the deployed git ref. The app's CI deploys a new image tag with a token that can do nothing else
(deploys.py). Each app keeps the name of its provider (core.hosting): RunPod, on the org's own key (the org
secret runpod_api_key), or This server, capped containers on the deployment's server.
"""

import json
import re
from typing import Any

from core import hosting, limits, secrets
from core.integrations import registry
from core.log import get_logger
from core.time import iso, utcnow
from hosting import base
from hosting import manifest as manifests
from hosting.base import SERVER, AppError
from hosting.models import App, AppDeployment
from modules.auth import scopes
from modules.uptime import service as uptime

logger = get_logger(__name__)

SECRET_PREFIX = "app_"  # nosec B105 - a secret name prefix, not a value
hosting.load()
registry.use("runpod", "hosting")
registry.use("github", "hosting")
secrets.declare_prefix(
    SECRET_PREFIX, "An env value for an app on a hosting provider, named in its manifest's secret_env"
)

scopes.declare("apps:read", "List the org's apps, their pods and deployments", uses=("runpod",))
scopes.declare("apps:manage", "Register app manifests and roll apps back", uses=("runpod", "github"))
scopes.declare("apps:deploy", "Deploy a new image tag of an app", uses=("runpod",))

APPS_LIMIT = "runpod.apps"
limits.declare(
    APPS_LIMIT,
    "hosting",
    "Hosting apps",
    25,
    unit="apps",
    usage=lambda db, org_id: db.query(App).filter_by(organization_id=org_id).count(),
)
SERVER_APPS_LIMIT = "runpod.server_apps"
SERVER_MEMORY_LIMIT = "runpod.server_memory_mb"


def _server_apps(db, org_id: int) -> list[App]:
    return db.query(App).filter_by(organization_id=org_id, provider=SERVER).all()


def server_memory(db, org_id: int, skip: str | None = None) -> int:
    """The memory in MB of the org's apps on This server, from their manifests, without the app named skip."""
    return sum(int(json.loads(str(a.manifest)).get("memory") or 0) for a in _server_apps(db, org_id) if a.name != skip)


limits.declare(
    SERVER_APPS_LIMIT,
    "hosting",
    "Apps on This server",
    2,
    unit="apps",
    usage=lambda db, org_id: len(_server_apps(db, org_id)),
)
limits.declare(
    SERVER_MEMORY_LIMIT,
    "hosting",
    "Memory of the apps on This server",
    1024,
    unit="MB",
    usage=server_memory,
)


def check_server(db, org_id: int, name: str, manifest: dict, new: bool) -> None:
    """The org's This server limits, for an app that takes the memory in its manifest."""
    if new:
        limits.check(db, org_id, SERVER_APPS_LIMIT)
    memory = int(manifest.get("memory") or 0)
    current = server_memory(db, org_id)
    after = server_memory(db, org_id, skip=name) + memory
    limits.check(db, org_id, SERVER_MEMORY_LIMIT, add=after - current)


def deployment_dict(d: AppDeployment) -> dict:
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


def app_dict(db, app: App) -> dict:
    latest = _latest(db, app)
    manifest = base.manifest_of(app)
    return {
        "name": app.name,
        "kind": manifest.get("kind", "service"),
        "description": manifest.get("description"),
        "url": manifest.get("url"),
        "host": app.provider,
        "provider": app.provider,
        "manifest": manifest,
        "repo": app.repo,
        "manifest_path": app.manifest_path,
        "pod_id": app.pod_id,
        "current_tag": app.current_tag,
        "latest_deployment": deployment_dict(latest) if latest else None,
        "updated_at": iso(app.updated_at),
    }


def put_app(
    db,
    org_id: int | None,
    name: str,
    manifest: Any = None,
    repo: Any = None,
    manifest_path: Any = None,
    provider: Any = None,
    pod_id: Any = None,
) -> dict:
    """Create an app or replace its manifest. Takes a manifest, or a repo whose manifest file is read
    now from the default branch and again at each deploy's ref. Commits.

    provider names the hosting provider of a new app, runpod when missing. An app with a pod keeps its provider.
    pod_id adopts a RunPod pod that already runs the app, so the next deploy updates it in place.
    """
    if not manifests.NAME_PATTERN.match(name):
        raise AppError("name must be lowercase letters, digits and single dashes, up to 63")
    if name == manifests.RESERVED_NAME:
        raise AppError(f"{manifests.RESERVED_NAME} is not available as an app name")
    if (manifest is None) == (repo is None):
        raise AppError("Send either manifest or repo")
    path = None
    if repo is not None:
        repo = manifests.safe_path(repo, manifests.REPO_PATTERN, "repo (owner/name)")
        path = manifests.safe_path(
            manifest_path or manifests.DEFAULT_MANIFEST_PATH, manifests.PATH_PATTERN, "manifest_path"
        )
        manifest = manifests.fetch_manifest(db, org_id, repo, path, None)
    app = db.query(App).filter_by(organization_id=org_id, name=name).first()
    new = app is None
    chosen = base.provider(provider).name if provider is not None else None
    target = chosen or (str(app.provider) if app is not None else hosting.DEFAULT)
    manifests.validated(manifest, target)
    if org_id is not None and "access" in manifest:
        raise AppError("Invalid manifest: access is only for shared apps")
    if target == SERVER and org_id is not None:
        check_server(db, org_id, name, manifest, new or app.provider != SERVER)
    if app is None:
        if org_id is not None:
            limits.check(db, org_id, APPS_LIMIT)
        app = App(organization_id=org_id, name=name, provider=chosen or hosting.DEFAULT)
        db.add(app)
    elif chosen is not None and chosen != app.provider:
        if app.pod_id:
            raise AppError("The app has a pod on its provider. Delete the app to move it to another provider", 409)
        app.provider = chosen
    if pod_id is not None:
        _take_pod(db, org_id, app, pod_id)
    app.repo, app.manifest_path = repo, path
    app.manifest = json.dumps(manifest, sort_keys=True)
    app.updated_at = utcnow()
    db.commit()
    if new and org_id is not None:
        uptime.watch_app(db, org_id, name)
    return app_dict(db, app)


POD_ID_PATTERN = re.compile(r"^[a-z0-9]{6,64}$")


def _take_pod(db, org_id: int | None, app: App, pod_id: Any) -> None:
    """Give app the RunPod pod pod_id that an officer names, after the org's RunPod key finds it."""
    if not isinstance(pod_id, str) or not POD_ID_PATTERN.match(pod_id):
        raise AppError("pod_id must be a RunPod pod id")
    if str(app.provider) != hosting.DEFAULT:
        raise AppError("Only an app on RunPod can adopt a pod")
    if app.pod_id and app.pod_id != pod_id:
        raise AppError("The app already has a pod", 409)
    try:
        found = base.client_for(db, org_id, hosting.DEFAULT).get_pod(pod_id)
    except hosting.HostingError as e:
        raise AppError(e.message, 502) from e
    if found is None:
        raise AppError("The org's RunPod key finds no pod with this id", 404)
    app.pod_id = pod_id


def list_apps(db, org_id: int | None) -> list[dict]:
    return [app_dict(db, a) for a in db.query(App).filter_by(organization_id=org_id).order_by(App.name).all()]


def get_app(db, org_id: int | None, name: str) -> dict:
    return app_dict(db, base.find(db, org_id, name))


def delete_app(db, org_id: int | None, name: str) -> dict:
    """Forget the app. On This server its container goes too; a RunPod pod keeps running until it is terminated
    on RunPod. Commits."""
    app = base.find(db, org_id, name)
    pod_id = app.pod_id
    if pod_id and app.provider == SERVER:
        try:
            base.client_for(db, org_id, SERVER).delete_pod(str(pod_id))
        except hosting.HostingError as e:
            if e.status != 404:
                raise AppError(f"The container was not removed: {e.message}", 502) from e
        pod_id = None
    db.query(AppDeployment).filter_by(app_id=app.id).delete(synchronize_session=False)
    if org_id is not None:
        uptime.forget_app(db, org_id, name)
    db.delete(app)
    db.commit()
    return {"deleted": True, "pod_id": pod_id}


def deployments(db, org_id: int | None, name: str, limit: int = 20) -> list[dict]:
    app = base.find(db, org_id, name)
    rows = (
        db.query(AppDeployment)
        .filter_by(app_id=app.id)
        .order_by(AppDeployment.started_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [deployment_dict(d) for d in rows]


def pod(db, org_id: int | None, name: str) -> dict | None:
    app = base.find(db, org_id, name)
    if not app.pod_id:
        return None
    try:
        return base.client_for(db, org_id, str(app.provider)).get_pod(str(app.pod_id))
    except hosting.HostingError as e:
        raise AppError(e.message, 502) from e


ACTIONS = ("start", "stop", "restart")
MAX_LOG_LINES = 1000


def _deployed(db, org_id: int | None, name: str) -> tuple[App, hosting.HostingClient]:
    app = base.find(db, org_id, name)
    if not app.pod_id:
        raise AppError("The app is not deployed yet", 409)
    return app, base.client_for(db, org_id, str(app.provider))


def app_action(db, org_id: int | None, name: str, action: Any) -> dict:
    """Start, stop or restart the app's pod or container. Returns the pod as its provider shows it."""
    if action not in ACTIONS:
        raise AppError(f"action must be one of {', '.join(ACTIONS)}")
    app, client = _deployed(db, org_id, name)
    pod_id = str(app.pod_id)
    act = {"start": client.start_pod, "stop": client.stop_pod, "restart": client.restart_pod}[action]
    try:
        act(pod_id)
        found = client.get_pod(pod_id)
    except hosting.HostingError as e:
        raise AppError(f"{action.capitalize()} failed: {e.message}", 502) from e
    logger.info("app %s app=%s org=%s", action, name, org_id)
    return {"action": action, "pod": found}


def app_logs(db, org_id: int | None, name: str, lines: Any = 200) -> dict:
    """The last lines of the app's output. This server only; RunPod shows logs in its own console."""
    if not isinstance(lines, int) or isinstance(lines, bool):
        lines = 200
    app, client = _deployed(db, org_id, name)
    read = getattr(client, "logs", None)
    if read is None:
        raise AppError(f"{base.provider_of(app).title} shows logs in its own console", 409)
    try:
        return {"logs": read(str(app.pod_id), max(1, min(lines, MAX_LOG_LINES)))}
    except hosting.HostingError as e:
        raise AppError(f"Logs could not be read: {e.message}", 502) from e
