"""Route helpers shared by modules that serve apps and agents over machine tokens."""

from flask import Blueprint, g, jsonify, request

from core.db import db_connect
from core.errors import ServiceError
from modules.auth.decoraters import auth_required, machine_scope_required
from modules.organizations.models import Organization

INACTIVE_ORG = "The token's organization is inactive or gone"


def json_body() -> dict:
    """The request's JSON object, or an empty dict when the body is missing or not an object."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def token_org(db) -> Organization | None:
    """The active organization of the calling machine token."""
    return db.query(Organization).filter_by(id=g.machine_caller.organization_id, is_active=True).first()


def machine_route(blueprint: Blueprint, rule: str, scope: str, methods: list[str]):
    """Register a route for machine tokens holding scope.

    The view gets (db, org, **path args) and returns a JSON-able value or a (body, status) tuple.
    A ServiceError becomes a JSON error with its status and rolls the session back.
    """

    def decorator(view):
        def wrapper(**kwargs):
            db = db_connect.SessionLocal()
            try:
                org = token_org(db)
                if org is None:
                    return jsonify({"error": INACTIVE_ORG}), 403
                result = view(db, org, **kwargs)
                return result if isinstance(result, tuple) else jsonify(result)
            except ServiceError as e:
                db.rollback()
                return jsonify({"error": e.message}), e.status
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        blueprint.route(rule, methods=methods)(machine_scope_required(scope)(wrapper))
        return view

    return decorator


def officer_route(blueprint: Blueprint, rule: str, methods: list[str]):
    """Register a route for officers of the organization named by <org_prefix> at the start of rule.

    The view gets (db, org, **path args) and returns a JSON-able value or a (body, status) tuple.
    A ServiceError becomes a JSON error with its status and rolls the session back.
    """

    def decorator(view):
        def wrapper(org_prefix, **kwargs):
            db = db_connect.SessionLocal()
            try:
                org = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()
                if org is None:
                    return jsonify({"error": "Organization not found"}), 404
                result = view(db, org, **kwargs)
                return result if isinstance(result, tuple) else jsonify(result)
            except ServiceError as e:
                db.rollback()
                return jsonify({"error": e.message}), e.status
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        blueprint.route(f"/<string:org_prefix>{rule}", methods=methods)(auth_required(wrapper))
        return view

    return decorator
