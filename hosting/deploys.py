"""App deploys: create or change the pod, adopt a pod a failed create left, health checks, rollback. No Flask here.

The first deploy creates the pod; later deploys change its image, which restarts it. A create can fail after
the provider made the pod: the call times out, or the provider answers 5xx. So a first deploy looks for a pod
with the app's pod name first, and again after such a failure, and adopts it instead of making a second one.
A job polls the health path and marks the deployment healthy or failed.
"""

import datetime
import json
from typing import Any, NoReturn, cast

from core import hosting, secrets, webhooks
from core.log import get_logger
from core.time import utcnow
from hosting import base, service
from hosting import manifest as manifests
from hosting.base import AppError
from hosting.models import App, AppDeployment
from modules.godfather.models import ComputePod

logger = get_logger(__name__)

webhooks.declare("app.deployed", "App deploys", "An app deploy ends: healthy, or failed with the reason.")

HEALTH_TIMEOUT = datetime.timedelta(minutes=15)
REDACTED = "(secret)"
FIRST_DEPLOY_RUNS = "The first deploy of this app still runs. Wait for it to finish, then deploy again"


def announce(app: App, deployment: AppDeployment) -> None:
    """Send the app.deployed webhook event for a deployment that ended."""
    healthy = deployment.status == "healthy"
    fields = [("Tag", str(deployment.tag)), ("By", str(deployment.actor or "-"))]
    if not healthy:
        fields.append(("Error", str(deployment.error or "-")))
    message = webhooks.Message(
        title=f"App {app.name} {'is healthy' if healthy else 'deploy failed'}",
        fields=tuple(fields),
        color=webhooks.GREEN if healthy else webhooks.RED,
    )
    webhooks.emit(cast(int, app.organization_id), "app.deployed", message)


def _env(db, org_id: int | None, manifest: dict, redact: bool) -> dict[str, str]:
    env = dict(manifest.get("env") or {})
    for var, secret_name in (manifest.get("secret_env") or {}).items():
        if redact:
            env[var] = REDACTED
            continue
        if org_id is None:
            value = secrets.get_deployment_secret(db, secret_name)
        else:
            value = secrets.get_secret(db, org_id, secret_name)
        if value is None:
            raise AppError(f"The org secret {secret_name} for {var} is not set", 409)
        env[var] = value
    return env


class _Call:
    """What a deploy sends: the image, the env, and the provider request for a pod id."""

    def __init__(
        self, db, org_id: int | None, org_prefix: str | None, app: App, manifest: dict, tag: str, redact: bool
    ):
        self.app, self.org_prefix, self.manifest = app, org_prefix, manifest
        self.image = f"{manifest['image']}@{tag}" if tag.startswith("sha256:") else f"{manifest['image']}:{tag}"
        self.env = _env(db, org_id, manifest, redact)
        self._create: tuple[str, str, dict] | None = None

    def request(self, pod_id: str | None, client: hosting.HostingClient | None) -> tuple[str, str, dict]:
        """The provider call: create the pod when pod_id is None, else change that pod.

        The create call is made once, because a provider may read its catalog for it. Raises AppError: 502
        when the provider did not answer, else 400.
        """
        if pod_id is None and self._create is not None:
            return self._create
        provider = base.provider_of(self.app)
        try:
            found = provider.request(
                str(self.app.name), self.org_prefix, pod_id, self.manifest, self.image, self.env, client
            )
        except hosting.HostingError as e:
            raise AppError(f"{provider.title}: {e.message}", 502 if hosting.retryable(e) else 400) from e
        if pod_id is None:
            self._create = found
        return found


def _claim(db, app: App) -> None:
    """Lock the app row until the next commit and refuse a deploy while the first deploy creates the pod.

    The update locks the row on Postgres and takes the write lock on SQLite, so a second deploy waits here
    and then reads the pod id and deployments that the first deploy committed.
    """
    db.query(App).filter(App.id == app.id).update({App.id: App.id}, synchronize_session=False)
    db.refresh(app)
    if app.pod_id:
        return
    creating = db.query(AppDeployment.id).filter_by(app_id=app.id, status="deploying").first()
    if creating is not None:
        db.rollback()
        raise AppError(FIRST_DEPLOY_RUNS, 409)


def _held(db, app: App) -> set[str]:
    """The pod ids that another app or a Godfather pod of the org already has, so a deploy never adopts them."""
    apps = db.query(App.pod_id).filter(
        App.organization_id.is_(None) if app.organization_id is None else App.organization_id == app.organization_id,
        App.provider == app.provider,
        App.id != app.id,
        App.pod_id.isnot(None),
    )
    held = {str(pod_id) for (pod_id,) in apps}
    if app.organization_id is not None:
        pods = db.query(ComputePod.pod_id).filter_by(organization_id=app.organization_id, provider=app.provider)
        held |= {str(pod_id) for (pod_id,) in pods}
    return held


def _adoptable(db, app: App, client: hosting.HostingClient, name: str) -> str | None:
    """The id of a pod on the account with the app's pod name that nothing here has, or None."""
    found = hosting.find_by_name(base.provider_of(app), client, name, _held(db, app))
    if found is None:
        return None
    logger.info("deploy adopts pod app=%s org=%s pod=%s", app.name, app.organization_id, found.get("id"))
    return str(found["id"])


def _create(db, app: App, client: hosting.HostingClient, call: _Call) -> None:
    """Give the app its pod: adopt the pod with its name, or create one. Sets app.pod_id.

    Raises HostingError when the provider fails, AppError when it cannot place the manifest.
    """
    _, _, body = call.request(None, client)
    name = str(body["name"])
    pod_id = _adoptable(db, app, client, name)
    if pod_id is None:
        try:
            created = client.create_pod(dict(body))
        except hosting.HostingError as e:
            pod_id = _adoptable(db, app, client, name) if hosting.retryable(e) else None
            if pod_id is None:
                raise
            logger.warning("create failed and a pod with the name exists app=%s error=%s", app.name, e.message)
        else:
            app.pod_id = str(created["id"])
            return
    client.update_pod(pod_id, call.request(pod_id, client)[2])
    app.pod_id = pod_id


def _fail(db, app: App, deployment: AppDeployment, error: str, cause: Exception) -> NoReturn:
    """Record the deployment as failed, send the event, and raise AppError 502."""
    deployment.status, deployment.finished_at, deployment.error = "failed", utcnow(), error
    db.commit()
    announce(app, deployment)
    raise AppError(f"Deploy failed: {error}", 502) from cause


def deploy(
    db,
    org_id: int | None,
    org_prefix: str | None,
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
    if not isinstance(tag, str) or not manifests.TAG_PATTERN.match(tag):
        raise AppError("tag must be an image tag or a sha256 digest")
    app = base.find(db, org_id, name)
    manifest_ref = None
    if manifest is None and app.repo:
        manifest_ref = manifests.safe_path(ref, manifests.REF_PATTERN, "ref") if ref is not None else None
        manifest = manifests.fetch_manifest(db, org_id, str(app.repo), str(app.manifest_path), manifest_ref)
    elif ref is not None and manifest is None:
        raise AppError("ref applies only to apps registered with a repo")
    manifest = manifest if manifest is not None else base.manifest_of(app)
    manifests.validated(manifest, str(app.provider))
    if app.provider == base.SERVER and org_id is not None:
        service.check_server(db, org_id, name, manifest, new=False)
    pod_id = str(app.pod_id) if app.pod_id else None
    if dry_run:
        try:
            preview_client = base.client_for(db, org_id, str(app.provider))
        except AppError:
            preview_client = None
        call = _Call(db, org_id, org_prefix, app, manifest, tag, redact=True)
        method, path, body = call.request(pod_id, preview_client)
        return {
            "dry_run": True,
            "tag": tag,
            "manifest": manifest,
            "request": {"method": method, "path": path, "body": body},
        }

    client = base.client_for(db, org_id, str(app.provider))
    call = _Call(db, org_id, org_prefix, app, manifest, tag, redact=False)
    if not app.pod_id:
        # Checks the create call before the claim, so a manifest the provider cannot place records no deploy
        call.request(None, client)
    _claim(db, app)
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
    # The deploying row without a pod id is the claim that _claim refuses; the commit ends the lock
    db.commit()
    try:
        if not app.pod_id:
            _create(db, app, client, call)
        else:
            updated = client.update_pod(str(app.pod_id), call.request(str(app.pod_id), client)[2])
            # This server moves a container with a legacy name to its new name
            if app.provider == base.SERVER and isinstance(updated, dict) and updated.get("id"):
                app.pod_id = str(updated["id"])
    except (hosting.HostingError, AppError) as e:
        _fail(db, app, deployment, e.message, e)
    except (KeyError, TypeError) as e:
        _fail(db, app, deployment, f"{base.provider_of(app).title} returned no pod id", e)
    app.current_tag, app.updated_at = tag, utcnow()
    db.commit()
    logger.info("deploy started app=%s tag=%s pod=%s", app.name, tag, app.pod_id)
    return {"deployment": service.deployment_dict(deployment), "pod_id": app.pod_id}


def rollback(
    db, org_id: int | None, org_prefix: str | None, name: str, actor: str | None, dry_run: bool = False
) -> dict:
    """Deploy the newest healthy tag other than the current one, with the manifest it ran with."""
    app = base.find(db, org_id, name)
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


def _check(health: dict) -> str | None:
    """The health check a provider runs: an HTTP path, None for a TCP connect, or "running" for the state alone."""
    if health.get("running"):
        return "running"
    return health.get("path")


def check_deployments(db, now: datetime.datetime | None = None) -> dict:
    """Mark running deployments healthy when their health path answers, failed after HEALTH_TIMEOUT. Commits."""
    now = now or utcnow()
    counts = {"healthy": 0, "failed": 0, "waiting": 0}
    ended = []
    running = db.query(AppDeployment, App).join(App, App.id == AppDeployment.app_id)
    for deployment, app in running.filter(AppDeployment.status == "deploying").all():
        health = base.manifest_of(app)["health"]
        if app.pod_id and base.provider_of(app).healthy(str(app.pod_id), health.get("port", 0), _check(health)):
            deployment.status, deployment.finished_at = "healthy", now
            counts["healthy"] += 1
            ended.append((app, deployment))
        elif deployment.started_at <= now - HEALTH_TIMEOUT:
            deployment.status, deployment.finished_at = "failed", now
            deployment.error = "The health path did not answer in time"
            counts["failed"] += 1
            ended.append((app, deployment))
        else:
            counts["waiting"] += 1
    db.commit()
    for app, deployment in ended:
        announce(app, deployment)
    return counts
