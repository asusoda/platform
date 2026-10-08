"""HTTP routes for knowledge sources and search. Machine tokens only; the organization is the token's."""

from flask import Blueprint, g, jsonify, request

from core import audit_http
from modules.auth.decoraters import machine_scope_required
from modules.organizations.models import Organization
from shared import db_connect

from . import embedder, service

knowledge_blueprint = Blueprint("knowledge", __name__)

# Searches are reads sent as POST
audit_http.SKIPPED_ROUTES.add("/api/knowledge/search")


def _route(rule: str, scope: str, methods: list[str]):
    """Register a machine route. The view gets (db, org, **path args) and returns a JSON-able value or a response."""

    def decorator(view):
        def wrapper(**kwargs):
            db = db_connect.SessionLocal()
            try:
                org = db.query(Organization).filter_by(id=g.machine_caller.organization_id, is_active=True).first()
                if org is None:
                    return jsonify({"error": "The token's organization is inactive or gone"}), 403
                result = view(db, org, **kwargs)
                return result if isinstance(result, tuple) else jsonify(result)
            except service.KnowledgeError as e:
                db.rollback()
                return jsonify({"error": e.message}), e.status
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        knowledge_blueprint.route(rule, methods=methods)(machine_scope_required(scope)(wrapper))
        return view

    return decorator


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@_route("/sources", "knowledge:read", ["GET"])
def list_sources(db, org):
    return {"sources": service.list_sources(db, int(org.id), request.args.get("category"))}


@_route("/sources/<path:key>", "knowledge:read", ["GET"])
def get_source(db, org, key):
    return service.get_source(db, int(org.id), key)


@_route("/sources/<path:key>", "knowledge:write", ["PUT"])
def put_source(db, org, key):
    result = service.put_source(db, int(org.id), str(org.prefix), key, _body(), embedder.configured())
    return result, 200 if result["changed"] is False else 201


@_route("/sources/<path:key>", "knowledge:write", ["DELETE"])
def delete_source(db, org, key):
    service.delete_source(db, int(org.id), key)
    return {"deleted": True}


@_route("/search", "knowledge:read", ["POST"])
def search(db, org):
    data = _body()
    return service.search(
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
