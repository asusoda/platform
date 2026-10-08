"""HTTP routes for knowledge sources and search. Machine tokens only; the organization is the token's."""

from functools import partial

from flask import Blueprint, request

from core.http import audit_hook
from core.http.responses import json_body
from modules.auth.routes import machine_route

from . import embedder, service
from .search import search as search_chunks

knowledge_blueprint = Blueprint("knowledge", __name__)
_route = partial(machine_route, knowledge_blueprint)

# Searches are reads sent as POST
audit_hook.SKIPPED_ROUTES.add("/api/knowledge/search")


@_route("/sources", "knowledge:read", ["GET"])
def list_sources(db, org):
    return {"sources": service.list_sources(db, int(org.id), request.args.get("category"))}


@_route("/sources/<path:key>", "knowledge:read", ["GET"])
def get_source(db, org, key):
    return service.get_source(db, int(org.id), key)


@_route("/sources/<path:key>", "knowledge:write", ["PUT"])
def put_source(db, org, key):
    result = service.put_source(db, int(org.id), str(org.prefix), key, json_body(), embedder.configured())
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
        embedder=embedder.configured(),
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
