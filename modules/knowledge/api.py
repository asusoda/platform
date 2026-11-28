"""HTTP routes for knowledge sources, search, shared sub-modules and live queries. Machine tokens only; the
organization is the token's.

/api/submodules serves the shared sub-modules of every module (knowledge.asu, feeds.jobs, feeds.hackathons) and the
live queries of knowledge content. /api/asu keeps the routes of the old asu module for clients that still call them.
"""

from functools import partial

from flask import Blueprint, request

from core.http import audit_hook
from core.http.responses import json_body
from modules.auth.routes import machine_route

from . import discover, embedder, service, shared
from .search import search as search_chunks

knowledge_blueprint = Blueprint("knowledge", __name__)
_route = partial(machine_route, knowledge_blueprint, module="knowledge")
submodules_blueprint = Blueprint("submodules", __name__)
_shared_route = partial(machine_route, submodules_blueprint, module="knowledge")
# The switch of a shared sub-module is its own, so no module switch gates the subscription routes
_switch_route = partial(machine_route, submodules_blueprint)
asu_blueprint = Blueprint("asu", __name__)
_asu_route = partial(machine_route, asu_blueprint, module="knowledge")

# Searches and live queries are reads sent as POST
audit_hook.SKIPPED_ROUTES.add("/api/knowledge/search")
audit_hook.SKIPPED_ROUTES.add("/api/submodules/<string:name>/query")
audit_hook.SKIPPED_ROUTES.add("/api/asu/query")


@_route("/sources", "knowledge:read", ["GET"])
def list_sources(db, org):
    return {"sources": service.list_sources(db, int(org.id), request.args.get("category"))}


@_route("/sources/<path:key>", "knowledge:read", ["GET"])
def get_source(db, org, key):
    return service.get_source(db, int(org.id), key)


@_route("/sources/<path:key>", "knowledge:write", ["PUT"])
def put_source(db, org, key):
    result = service.put_source(db, int(org.id), str(org.prefix), key, json_body(), embedder.for_org(db, int(org.id)))
    return result, 200 if result["changed"] is False else 201


@_route("/sources/<path:key>", "knowledge:write", ["DELETE"])
def delete_source(db, org, key):
    service.delete_source(db, int(org.id), key)
    return {"deleted": True}


@_route("/search", "knowledge:read", ["POST"])
def search(db, org):
    data = json_body()
    return search_chunks(
        db,
        int(org.id),
        data.get("query"),
        category=data.get("category"),
        top_k=data.get("top_k"),
        window=data.get("window"),
        embedding=data.get("embedding"),
        embedding_model=data.get("embedding_model"),
        embedder=embedder.for_org(db, int(org.id)),
    )


# Crawled sources


@_route("/crawls/<path:key>", "knowledge:write", ["PUT"])
def schedule_crawl(db, org, key):
    from . import crawl

    return crawl.schedule(db, int(org.id), str(org.prefix), key, json_body())


@_route("/crawls/run", "knowledge:write", ["POST"])
def run_crawl(db, org):
    """Queue a crawl of one source now."""
    from . import crawl

    data = json_body()
    crawl.queue(db, int(org.id), str(org.prefix), str(data.get("key")), force=data.get("force") is True)
    return {"queued": True}, 202


# Pages an agent read


@_route("/discovered", "knowledge:discover", ["POST"])
def discovered(db, org):
    """Save a page an agent read: at once for an ASU page, after an officer approves for others."""
    result = discover.discover(db, int(org.id), json_body().get("url"))
    return result, 201 if result["status"] != "known" else 200


# Shared sub-modules and live queries


@_shared_route("", "knowledge:read", ["GET"])
def list_submodules(db, org):
    return {"submodules": shared.list_submodules(db, int(org.id))}


@_shared_route("/<string:name>/queries", "knowledge:read", ["GET"])
def list_queries(db, org, name):
    return {"queries": shared.query_sources(name)}


@_shared_route("/<string:name>/query", "knowledge:read", ["POST"])
def run_query(db, org, name):
    data = json_body()
    return shared.query(db, int(org.id), str(org.prefix), name, data.get("source"), data.get("params"))


@_switch_route("/<string:name>/subscription", "submodules:manage", ["PUT"])
def subscribe(db, org, name):
    """Turn the shared sub-module on for the token's org: its pages, feeds and other parts."""
    return shared.subscribe(db, org, name, actor="machine")


@_switch_route("/<string:name>/subscription", "submodules:manage", ["DELETE"])
def unsubscribe(db, org, name):
    return shared.unsubscribe(db, org, name)


@_shared_route("/<string:name>/sync", "knowledge:write", ["POST"])
def sync_submodule(db, org, name):
    """Older name of PUT /<name>/subscription."""
    return shared.sync(db, org, name)


@_asu_route("/queries", "knowledge:read", ["GET"])
def asu_queries(db, org):
    return {"queries": shared.query_sources("asu")}


@_asu_route("/query", "knowledge:read", ["POST"])
def asu_query(db, org):
    data = json_body()
    return shared.query(db, int(org.id), str(org.prefix), "asu", data.get("source"), data.get("params"))


@_asu_route("/sync", "knowledge:write", ["POST"])
def asu_sync(db, org):
    return shared.sync(db, org, "asu")
