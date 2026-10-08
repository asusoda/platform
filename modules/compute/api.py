"""HTTP routes for pods. Officers manage an org's pods; members list and connect to the ones shared with them."""

from typing import cast

from flask import Blueprint, jsonify, request

from modules.auth import access
from modules.auth.decoraters import auth_required, member_required
from modules.organizations.models import Organization
from shared import db_connect

from . import service

compute_blueprint = Blueprint("compute", __name__)


def _body():
    return request.get_json(silent=True)


def _officer_route(rule: str, methods: list[str]):
    """An officer route under /<org_prefix>. The view gets (db, org, **path args)."""

    def decorator(view):
        def wrapper(org_prefix, **kwargs):
            db = db_connect.SessionLocal()
            try:
                org = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()
                if org is None:
                    return jsonify({"error": "Organization not found"}), 404
                result = view(db, org, **kwargs)
                return result if isinstance(result, tuple) else jsonify(result)
            except service.ComputeError as e:
                db.rollback()
                return jsonify({"error": e.message}), e.status
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        compute_blueprint.route(f"/<string:org_prefix>{rule}", methods=methods)(auth_required(wrapper))
        return view

    return decorator


def _member_route(rule: str, methods: list[str]):
    """A member route under /<org_prefix>/me. The view gets (db, org, discord_id, **path args)."""

    def decorator(view):
        def wrapper(org_prefix, user_discord_id=None, organization=None, **kwargs):
            db = db_connect.SessionLocal()
            try:
                result = view(db, organization, str(user_discord_id), **kwargs)
                return result if isinstance(result, tuple) else jsonify(result)
            except service.ComputeError as e:
                db.rollback()
                return jsonify({"error": e.message}), e.status
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        compute_blueprint.route(f"/<string:org_prefix>/me{rule}", methods=methods)(member_required(wrapper))
        return view

    return decorator


def _org_id(org) -> int:
    return cast(int, org.id)


def _caller() -> str | None:
    principal = access.current_principal()
    return principal.discord_id if principal else None


@_officer_route("/pods", ["GET"])
def list_pods(db, org):
    return {"pods": service.list_pods(db, _org_id(org))}


@_officer_route("/pods", ["POST"])
def create_pod(db, org):
    return {"pod": service.create_pod(db, _org_id(org), _body(), _caller())}, 201


@_officer_route("/pods/<string:pod_id>", ["GET"])
def get_pod(db, org, pod_id):
    return {"pod": service.get_pod(db, _org_id(org), pod_id)}


@_officer_route("/pods/<string:pod_id>", ["PUT"])
def update_pod(db, org, pod_id):
    return {"pod": service.update_pod(db, _org_id(org), pod_id, _body())}


@_officer_route("/pods/<string:pod_id>/action", ["POST"])
def pod_action(db, org, pod_id):
    data = _body()
    return service.act(db, _org_id(org), pod_id, data.get("action") if isinstance(data, dict) else None)


@_member_route("/pods", ["GET"])
def my_pods(db, org, discord_id):
    return {"pods": service.accessible_pods(db, _org_id(org), discord_id)}


def _is_officer(org, discord_id: str) -> bool:
    if access.is_superadmin(discord_id):
        return True
    guilds = access.officer_guild_ids(discord_id)
    return guilds is not None and str(org.guild_id) in guilds


def _username(org, discord_id: str) -> str:
    directory = access.discord_directory()
    member = directory.get_member(org.guild_id, discord_id) if directory is not None else None
    return str(((member or {}).get("user") or {}).get("username") or discord_id)


@_member_route("/pods/<string:pod_id>/connect", ["POST"])
def connect(db, org, discord_id, pod_id):
    data = _body()
    public_key = data.get("public_key") if isinstance(data, dict) else None
    return {
        "ssh_info": service.connect(
            db, _org_id(org), pod_id, discord_id, _username(org, discord_id), _is_officer(org, discord_id), public_key
        )
    }
