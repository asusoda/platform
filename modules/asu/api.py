"""HTTP routes for ASU sources and live queries. Machine tokens only; the organization is the token's."""

from flask import Blueprint, g, jsonify, request

from core import audit_http
from modules.auth.decoraters import machine_scope_required
from modules.knowledge.service import KnowledgeError
from modules.organizations.models import Organization
from shared import db_connect

from . import service

asu_blueprint = Blueprint("asu", __name__)

# Live queries are reads sent as POST
audit_http.SKIPPED_ROUTES.add("/api/asu/query")


def _org(db):
    return db.query(Organization).filter_by(id=g.machine_caller.organization_id, is_active=True).first()


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@asu_blueprint.route("/queries", methods=["GET"])
@machine_scope_required("knowledge:read")
def list_queries():
    return jsonify({"queries": service.query_sources()})


@asu_blueprint.route("/query", methods=["POST"])
@machine_scope_required("knowledge:read")
def run_query():
    data = _body()
    db = db_connect.SessionLocal()
    try:
        org = _org(db)
        if org is None:
            return jsonify({"error": "The token's organization is inactive or gone"}), 403
        return jsonify(service.query(db, int(org.id), str(org.prefix), data.get("source"), data.get("params")))
    except KnowledgeError as e:
        return jsonify({"error": e.message}), e.status
    finally:
        db.close()


@asu_blueprint.route("/sync", methods=["POST"])
@machine_scope_required("knowledge:write")
def sync_sources():
    """Register every ASU page as a crawled source of the token's org."""
    db = db_connect.SessionLocal()
    try:
        org = _org(db)
        if org is None:
            return jsonify({"error": "The token's organization is inactive or gone"}), 403
        return jsonify(service.sync(db, int(org.id), str(org.prefix)))
    finally:
        db.close()
