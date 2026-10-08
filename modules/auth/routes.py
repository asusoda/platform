"""Route registration for officer, member and machine-token views.

Each view gets a database session and the org and returns a JSON-able value, a (body, status)
tuple or a response. A ServiceError becomes {"error": message} with its status and rolls the
session back.
"""

from flask import Blueprint, Response, g, jsonify

from core.db import db_connect
from core.errors import ServiceError
from core.http.responses import error
from modules.auth.decorators import auth_required, machine_scope_required, member_required
from modules.organizations.models import Organization

INACTIVE_ORG = "The token's organization is inactive or gone"


def token_org(db) -> Organization | None:
    """The active organization of the calling machine token."""
    return db.query(Organization).filter_by(id=g.machine_caller.organization_id, is_active=True).first()


def respond(db, view, *args, **kwargs):
    """Call view(db, *args, **kwargs) and make its result or ServiceError a response."""
    try:
        result = view(db, *args, **kwargs)
        return result if isinstance(result, tuple | Response) else jsonify(result)
    except ServiceError as e:
        db.rollback()
        return error(e.message, e.status)


def machine_route(blueprint: Blueprint, rule: str, scope: str, methods: list[str]):
    """Register a route for machine tokens holding scope. The view gets (db, org, **path args)."""

    def decorator(view):
        def wrapper(**kwargs):
            db = db_connect.SessionLocal()
            try:
                org = token_org(db)
                if org is None:
                    return error(INACTIVE_ORG, 403)
                return respond(db, view, org, **kwargs)
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        blueprint.route(rule, methods=methods)(machine_scope_required(scope)(wrapper))
        return view

    return decorator


def officer_route(blueprint: Blueprint, rule: str, methods: list[str]):
    """Register a route under /<org_prefix> for officers of that active org. The view gets (db, org, **path args)."""

    def decorator(view):
        def wrapper(org_prefix, **kwargs):
            db = db_connect.SessionLocal()
            try:
                org = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()
                if org is None:
                    return error("Organization not found", 404)
                return respond(db, view, org, **kwargs)
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        blueprint.route(f"/<string:org_prefix>{rule}", methods=methods)(auth_required(wrapper))
        return view

    return decorator


def member_view(view):
    """Wrap a view for members signed in with Discord (member_required). It gets (db, org, discord_id, **path args)."""

    def wrapper(org_prefix, user_discord_id=None, organization=None, **kwargs):
        db = db_connect.SessionLocal()
        try:
            return respond(db, view, organization, str(user_discord_id), **kwargs)
        finally:
            db.close()

    wrapper.__name__ = view.__name__
    return member_required(wrapper)
