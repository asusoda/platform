"""HTTP routes for the officer dashboard: the overview, branding, CI runs, and officer control of apps and knowledge.

Apps and knowledge have machine-token routes in their own modules. The routes here call the same services for
officers who sign in to the dashboard.
"""

from functools import partial
from typing import cast

from flask import Blueprint, request

from core.http import audit_hook
from core.http.responses import json_body
from modules.auth import access
from modules.auth.routes import officer_route
from modules.knowledge import crawl, embedder
from modules.knowledge import service as knowledge
from modules.knowledge.search import search as search_chunks
from modules.organizations import service as organizations
from modules.runpod import service as apps

from . import ci, service

dashboard_blueprint = Blueprint("dashboard", __name__)
_route = partial(officer_route, dashboard_blueprint)

# Searches are reads sent as POST
audit_hook.SKIPPED_ROUTES.add("/api/dashboard/<string:org_prefix>/knowledge/search")


def _org_id(org) -> int:
    return cast(int, org.id)


def _actor() -> str:
    principal = access.current_principal()
    return f"officer:{principal.discord_id}" if principal and principal.discord_id else "officer"


@_route("/overview", ["GET"])
def overview(db, org):
    return service.overview(db, org)


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
    return {"sources": knowledge.list_sources(db, _org_id(org), request.args.get("category"))}


@_route("/knowledge/sources/<path:key>", ["DELETE"])
def delete_source(db, org, key):
    knowledge.delete_source(db, _org_id(org), key)
    return {"deleted": True}


@_route("/knowledge/crawls/<path:key>", ["PUT"])
def schedule_crawl(db, org, key):
    return crawl.schedule(db, _org_id(org), str(org.prefix), key, json_body())


@_route("/knowledge/crawls/<path:key>/run", ["POST"])
def run_crawl(db, org, key):
    """Queue a crawl of one source now. The result shows on the source as last_attempt_at and last_error."""
    from core.jobs import defer

    source = knowledge.get_source(db, _org_id(org), key)
    if source["crawl"] is None:
        raise knowledge.KnowledgeError("This source is written by a client, not crawled", 409)
    force = json_body().get("force") is True
    defer("knowledge.crawl_source", org_id=_org_id(org), key=key, force=force, org_prefix=str(org.prefix))
    return {"queued": True}, 202


@_route("/knowledge/search", ["POST"])
def search(db, org):
    data = json_body()
    return search_chunks(
        db,
        _org_id(org),
        data.get("query"),
        category=data.get("category"),
        top_k=data.get("top_k"),
        embedder=embedder.configured(),
    )
