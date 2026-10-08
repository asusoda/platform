"""HTTP routes for apps on RunPod. Machine tokens only; the organization is the token's."""

from typing import cast

from flask import Blueprint, g, jsonify, request

from modules.auth.decoraters import machine_scope_required
from modules.organizations.models import Organization
from shared import db_connect

from . import service

apps_blueprint = Blueprint("apps", __name__)


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
            except service.AppError as e:
                db.rollback()
                return jsonify({"error": e.message}), e.status
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        apps_blueprint.route(rule, methods=methods)(machine_scope_required(scope)(wrapper))
        return view

    return decorator


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _actor() -> str:
    caller = g.machine_caller
    return f"{caller.kind}:{caller.name}#{caller.token_id}"


def _org_id(org) -> int:
    return cast(int, org.id)


@_route("", "apps:read", ["GET"])
def list_apps(db, org):
    return {"apps": service.list_apps(db, _org_id(org))}


@_route("/<string:name>", "apps:read", ["GET"])
def get_app(db, org, name):
    return service.get_app(db, _org_id(org), name)


@_route("/<string:name>", "apps:manage", ["PUT"])
def put_app(db, org, name):
    return service.put_app(db, _org_id(org), name, _body().get("manifest"))


@_route("/<string:name>", "apps:manage", ["DELETE"])
def delete_app(db, org, name):
    return service.delete_app(db, _org_id(org), name)


@_route("/<string:name>/deployments", "apps:read", ["GET"])
def list_deployments(db, org, name):
    return {"deployments": service.deployments(db, _org_id(org), name)}


@_route("/<string:name>/pod", "apps:read", ["GET"])
def get_pod(db, org, name):
    return {"pod": service.pod(db, _org_id(org), name)}


@_route("/<string:name>/deploy", "apps:deploy", ["POST"])
def deploy(db, org, name):
    data = _body()
    result = service.deploy(
        db, _org_id(org), str(org.prefix), name, data.get("tag"), _actor(), dry_run=data.get("dry_run") is True
    )
    return result, 200 if result.get("dry_run") else 202


@_route("/<string:name>/rollback", "apps:manage", ["POST"])
def rollback(db, org, name):
    result = service.rollback(db, _org_id(org), str(org.prefix), name, _actor(), dry_run=_body().get("dry_run") is True)
    return result, 200 if result.get("dry_run") else 202
