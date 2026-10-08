"""HTTP routes for the officer dashboard: the overview, branding, CI runs, and officer control of apps and knowledge.

Apps and knowledge have machine-token routes in their own modules. The routes here call the same services for
officers who sign in to the dashboard.
"""

from functools import partial
from typing import cast

from flask import Blueprint, request

from core import secrets
from core.http import audit_hook
from core.http.responses import json_body
from core.integrations import registry as integrations
from modules.auth import access
from modules.auth.routes import officer_route
from modules.knowledge import crawl, documents, embedder, packs, runs, settings
from modules.knowledge import service as knowledge
from modules.knowledge.search import search as search_chunks
from modules.organizations import service as organizations
from modules.runpod import service as apps

from . import ci, notices, service

dashboard_blueprint = Blueprint("dashboard", __name__)
_route = partial(officer_route, dashboard_blueprint)

# Searches are reads sent as POST
audit_hook.SKIPPED_ROUTES.add("/api/dashboard/<string:org_prefix>/knowledge/search")
audit_hook.SKIPPED_ROUTES.add("/api/dashboard/<string:org_prefix>/integrations/<string:key>/test")


def _org_id(org) -> int:
    return cast(int, org.id)


def _actor() -> str:
    principal = access.current_principal()
    return f"officer:{principal.discord_id}" if principal and principal.discord_id else "officer"


@_route("/overview", ["GET"])
def overview(db, org):
    return service.overview(db, org)


@_route("/notifications", ["GET"])
def list_notifications(db, org):
    return notices.listing(db, org)


@_route("/notifications/resolve", ["POST"])
def resolve_notifications(db, org):
    return notices.resolve(db, org, json_body().get("ids"), _actor())


@_route("/notifications/reopen", ["POST"])
def reopen_notifications(db, org):
    return notices.reopen(db, org, json_body().get("ids"))


@_route("/integrations", ["GET"])
def list_integrations(db, org):
    return {"integrations": integrations.status(db, _org_id(org)), "secrets_key": secrets.configured()}


@_route("/integrations/<string:key>", ["PUT"])
def save_integration(db, org, key):
    integrations.save(db, _org_id(org), key, json_body().get("fields"), _actor())
    return list_integrations(db, org)


@_route("/integrations/<string:key>/test", ["POST"])
def test_integration(db, org, key):
    try:
        return {"ok": True, "message": integrations.test(db, _org_id(org), key)}
    except integrations.IntegrationError as e:
        return {"ok": False, "message": e.message}


@_route("/branding", ["GET"])
def get_branding(db, org):
    return organizations.branding(org)


@_route("/branding", ["PUT"])
def set_branding(db, org):
    return organizations.set_branding(db, org, json_body())


@_route("/ci", ["GET"])
def ci_runs(db, org):
    return ci.runs(db, org)


@_route("/ci/repos", ["PUT"])
def set_ci_repos(db, org):
    return {"repos": ci.set_repos(db, org, json_body().get("repos"))}


# Apps on RunPod


@_route("/apps", ["GET"])
def list_apps(db, org):
    return {"apps": apps.list_apps(db, _org_id(org))}


@_route("/apps/<string:name>", ["GET"])
def get_app(db, org, name):
    return apps.get_app(db, _org_id(org), name) | {"deployments": apps.deployments(db, _org_id(org), name)}


@_route("/apps/<string:name>", ["PUT"])
def put_app(db, org, name):
    data = json_body()
    return apps.put_app(db, _org_id(org), name, data.get("manifest"), data.get("repo"), data.get("manifest_path"))


@_route("/apps/<string:name>", ["DELETE"])
def delete_app(db, org, name):
    return apps.delete_app(db, _org_id(org), name)


@_route("/apps/<string:name>/pod", ["GET"])
def get_app_pod(db, org, name):
    return {"pod": apps.pod(db, _org_id(org), name)}


@_route("/apps/<string:name>/deploy", ["POST"])
def deploy_app(db, org, name):
    data = json_body()
    dry_run = data.get("dry_run") is True
    result = apps.deploy(
        db, _org_id(org), str(org.prefix), name, data.get("tag"), _actor(), dry_run=dry_run, ref=data.get("ref")
    )
    return result, 200 if dry_run else 202


@_route("/apps/<string:name>/rollback", ["POST"])
def rollback_app(db, org, name):
    dry_run = json_body().get("dry_run") is True
    result = apps.rollback(db, _org_id(org), str(org.prefix), name, _actor(), dry_run=dry_run)
    return result, 200 if dry_run else 202


# Knowledge sources


@_route("/knowledge/sources", ["GET"])
def list_sources(db, org):
    sources = knowledge.list_sources(db, _org_id(org), request.args.get("category"))
    return {"sources": sources, "can_publish": knowledge.can_publish(db, str(org.prefix))}


@_route("/knowledge/sources/<path:key>", ["DELETE"])
def delete_source(db, org, key):
    knowledge.delete_source(db, _org_id(org), key)
    return {"deleted": True}


@_route("/knowledge/crawls/<path:key>", ["PUT"])
def schedule_crawl(db, org, key):
    return crawl.schedule(db, _org_id(org), str(org.prefix), key, json_body())


@_route("/knowledge/crawls/<path:key>/run", ["POST"])
def run_crawl(db, org, key):
    """Queue a crawl of one source now."""
    crawl.queue(db, _org_id(org), str(org.prefix), key, force=json_body().get("force") is True)
    return {"queued": True}, 202


@_route("/knowledge/packs", ["GET"])
def list_packs(db, org):
    return {"packs": packs.list_packs(db, _org_id(org))}


@_route("/knowledge/packs/<string:name>/sync", ["POST"])
def sync_pack(db, org, name):
    """Add or update the pack's sources, then start the crawl job for the sources that are due."""
    from core.jobs import defer

    counts = packs.sync(db, _org_id(org), str(org.prefix), name)
    defer("knowledge.crawl_due")
    return counts


@_route("/knowledge/search", ["POST"])
def search(db, org):
    data = json_body()
    return search_chunks(
        db,
        _org_id(org),
        data.get("query"),
        category=data.get("category"),
        top_k=data.get("top_k"),
        embedder=embedder.for_org(db, _org_id(org)),
    )


@_route("/knowledge/documents", ["POST"])
def upload_documents(db, org):
    """Index uploaded files. Form fields: files (one or more), category, folder, public."""
    uploads = [documents.Upload(f.filename or "document", f.read()) for f in request.files.getlist("files")]
    form = {"category": request.form.get("category"), "folder": request.form.get("folder")}
    form["public"] = request.form.get("public") == "true"
    return documents.upload(db, _org_id(org), str(org.prefix), uploads, form, embedder.for_org(db, _org_id(org)))


@_route("/knowledge/settings", ["GET"])
def get_knowledge_settings(db, org):
    return _settings_body(db, _org_id(org), settings.for_org(db, _org_id(org)))


@_route("/knowledge/settings", ["PUT"])
def set_knowledge_settings(db, org):
    return _settings_body(db, _org_id(org), settings.update(db, _org_id(org), json_body()))


def _settings_body(db, org_id: int, values: dict) -> dict:
    model = embedder.for_org(db, org_id)
    return {
        "settings": values,
        "defaults": settings.defaults(),
        "embeddings": {"configured": model is not None, "model": model.model if model else None},
    }


@_route("/knowledge/reindex", ["POST"])
def reindex(db, org):
    """Start a job that crawls every crawled source again, so new chunk settings apply."""
    from core.jobs import defer

    defer("knowledge.reindex", org_id=_org_id(org))
    return {"queued": True}, 202


@_route("/knowledge/runs", ["GET"])
def knowledge_runs(db, org):
    limit = request.args.get("limit", type=int)
    return {"runs": runs.recent(db, _org_id(org), limit, failed_only=request.args.get("failed") == "1")}
