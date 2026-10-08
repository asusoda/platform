"""HTTP routes for ASU sources and live queries. Machine tokens only; the organization is the token's."""

from functools import partial

from flask import Blueprint, jsonify

from core import audit_http
from modules.auth.decoraters import machine_scope_required
from modules.auth.routes import json_body, machine_route

from . import service

asu_blueprint = Blueprint("asu", __name__)
_route = partial(machine_route, asu_blueprint)

# Live queries are reads sent as POST
audit_http.SKIPPED_ROUTES.add("/api/asu/query")


@asu_blueprint.route("/queries", methods=["GET"])
@machine_scope_required("knowledge:read")
def list_queries():
    return jsonify({"queries": service.query_sources()})


@_route("/query", "knowledge:read", ["POST"])
def run_query(db, org):
    data = json_body()
    return service.query(db, int(org.id), str(org.prefix), data.get("source"), data.get("params"))


@_route("/sync", "knowledge:write", ["POST"])
def sync_sources(db, org):
    """Register every ASU page as a crawled source of the token's org."""
    return service.sync(db, int(org.id), str(org.prefix))
