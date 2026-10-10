"""HTTP routes for packs and their live queries. Machine tokens only; the organization is the token's.

/api/asu keeps the routes of the old asu module for clients that still call them.
"""

from functools import partial

from flask import Blueprint

from core.http import audit_hook
from core.http.responses import json_body
from modules.auth.routes import machine_route

from . import service

packs_blueprint = Blueprint("packs", __name__)
_route = partial(machine_route, packs_blueprint)
asu_blueprint = Blueprint("asu", __name__)
_asu_route = partial(machine_route, asu_blueprint)

# Live queries are reads sent as POST
audit_hook.SKIPPED_ROUTES.add("/api/packs/<string:name>/query")
audit_hook.SKIPPED_ROUTES.add("/api/asu/query")


@_route("", "knowledge:read", ["GET"])
def list_packs(db, org):
    return {"packs": service.list_packs(db, int(org.id))}


@_route("/<string:name>/queries", "knowledge:read", ["GET"])
def list_queries(db, org, name):
    return {"queries": service.query_sources(name)}


@_route("/<string:name>/query", "knowledge:read", ["POST"])
def run_query(db, org, name):
    data = json_body()
    return service.query(db, int(org.id), str(org.prefix), name, data.get("source"), data.get("params"))


@_route("/<string:name>/sync", "knowledge:write", ["POST"])
def sync_pack(db, org, name):
    """Register every page of the pack as a crawled source of the token's org."""
    return service.sync(db, int(org.id), str(org.prefix), name)


@_asu_route("/queries", "knowledge:read", ["GET"])
def asu_queries(db, org):
    return {"queries": service.query_sources("asu")}


@_asu_route("/query", "knowledge:read", ["POST"])
def asu_query(db, org):
    data = json_body()
    return service.query(db, int(org.id), str(org.prefix), "asu", data.get("source"), data.get("params"))


@_asu_route("/sync", "knowledge:write", ["POST"])
def asu_sync(db, org):
    return service.sync(db, int(org.id), str(org.prefix), "asu")
