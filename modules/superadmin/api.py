"""Superadmin routes under /api/superadmin. Each route reads the request and calls service.py or another module."""

from flask import Blueprint, jsonify, request

from core import audit, error_log
from core.db import db_connect
from core.errors import ServiceError
from core.http.responses import internal_error
from core.log import get_logger
from hosting import deploys, shared
from hosting import service as apps
from modules.auth.access import current_principal, discord_directory
from modules.auth.decorators import header_token_refusal, superadmin_required
from modules.auth.routes import respond
from modules.auth.tokens import token_manager

from . import service

logger = get_logger(__name__)

superadmin_blueprint = Blueprint("superadmin", __name__)


def _run(work, where: str | None = None):
    """work(db) in a new session, through respond. With where, any other exception gives internal_error(where)."""
    db = next(db_connect.get_db())
    try:
        return respond(db, work)
    except Exception:
        if where is None:
            raise
        db.rollback()
        return internal_error(where)
    finally:
        db.close()


def _actor() -> str:
    principal = current_principal()
    return f"superadmin:{principal.discord_id}" if principal and principal.discord_id else "superadmin"


@superadmin_blueprint.route("/check", methods=["GET"])
def check_superadmin():
    """Whether the caller is the superadmin: 200 when yes, 403 when no.

    It answers for the caller's own valid token only, so it does not need superadmin_required.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.error("superadmin check refused: no Bearer Authorization header")
            return jsonify({"error": "Authorization header required"}), 401

        token = auth_header.split(" ")[1]
        refusal = header_token_refusal(token)
        if refusal:
            return refusal
        token_data = token_manager.decode_token(token)
        if not token_data:
            logger.error("superadmin check refused: the token does not decode")
            return jsonify({"error": "Invalid token"}), 401

        user_discord_id = token_data.get("discord_id")
        if not user_discord_id:
            logger.error("superadmin check refused: the token has no discord_id")
            return jsonify({"error": "Token missing Discord ID"}), 401

        if service.is_superadmin(user_discord_id):
            return jsonify({"is_superadmin": True}), 200
        return jsonify({"is_superadmin": False}), 403
    except Exception:
        return internal_error("superadmin.check_superadmin")


@superadmin_blueprint.route("/dashboard", methods=["GET"])
@superadmin_required
def get_dashboard():
    """Guilds without an org, every org, and the orgs whose guild has the caller."""
    principal = current_principal()
    officer_id = principal.discord_id if principal else None
    return _run(lambda db: service.dashboard(db, discord_directory(), officer_id), "superadmin.get_dashboard")


@superadmin_blueprint.route("/orgs", methods=["GET"])
@superadmin_required
def get_orgs():
    """Every org with its members, modules on, limits near, open errors and last activity. Needs no bot."""
    return _run(lambda db: {"orgs": service.org_list(db)})


@superadmin_blueprint.route("/guild_roles/<guild_id>", methods=["GET"])
@superadmin_required
def get_guild_roles(guild_id):
    """The guild's roles, highest first, without @everyone and integration roles."""
    return _run(
        lambda db: {"roles": service.roles_of_guild(discord_directory(), guild_id)}, "superadmin.get_guild_roles"
    )


@superadmin_blueprint.route("/update_officer_role/<int:org_id>", methods=["PUT"])
@superadmin_required
def update_officer_role(org_id):
    """Set the org's officer role. An empty officer_role_id clears it."""
    return _run(
        lambda db: service.set_officer_role(db, discord_directory(), org_id, request.get_json()),
        "superadmin.update_officer_role",
    )


@superadmin_blueprint.route("/add_org/<guild_id>", methods=["POST"])
@superadmin_required
def add_organization(guild_id):
    """Add an org for a guild the bot is in, with default settings. 409 when the prefix or the guild is taken."""
    try:
        guild = service.find_guild(discord_directory(), guild_id)
    except ServiceError as e:
        return jsonify({"error": e.message}), e.status
    return _run(lambda db: {"message": f"Organization {service.add_organization(db, guild).name} added successfully!"})


@superadmin_blueprint.route("/remove_org/<int:org_id>", methods=["DELETE"])
@superadmin_required
def remove_organization(org_id):
    """Delete an org and the rows that belong to it. 409 while the org has apps or pods on a provider."""
    return _run(
        lambda db: {"message": f"Organization {service.delete_organization(db, org_id)} removed successfully!"},
        "superadmin.remove_organization",
    )


@superadmin_blueprint.route("/audit", methods=["GET"])
@superadmin_required
def get_audit():
    """Audit log across all orgs, newest first. ?org=<prefix>&limit=100&before_id=<id>."""
    org = request.args.get("org")
    limit = request.args.get("limit", 100, type=int)
    before_id = request.args.get("before_id", type=int)
    return _run(lambda db: {"entries": audit.list_entries(db, org=org, limit=limit, before_id=before_id)})


@superadmin_blueprint.route("/publishers", methods=["GET"])
@superadmin_required
def get_publishers():
    """Orgs that may write knowledge every org can search, and where the right comes from."""
    from modules.knowledge import service as knowledge

    return _run(lambda db: {"publishers": knowledge.publishers(db)})


@superadmin_blueprint.route("/publishers/<int:org_id>", methods=["PUT"])
@superadmin_required
def put_publisher(org_id):
    """Mark or unmark an org as a knowledge publisher. Body: {"publisher": true}."""
    from modules.knowledge import service as knowledge

    data = request.get_json(silent=True) or {}
    return _run(lambda db: {"publishers": knowledge.set_publisher(db, org_id, data.get("publisher"))})


@superadmin_blueprint.route("/errors", methods=["GET"])
@superadmin_required
def get_errors():
    """Errors of every org and of the whole server, newest first. ?org=<prefix>&status=open|resolved|all."""
    org = request.args.get("org") or None
    status = request.args.get("status", "open")
    limit = request.args.get("limit", 100, type=int)
    return _run(lambda db: {"errors": error_log.list_groups(db, org=org, everything=True, status=status, limit=limit)})


@superadmin_blueprint.route("/errors/<string:action>", methods=["POST"])
@superadmin_required
def change_errors(action):
    """Resolve or reopen errors of any org. Body: {"ids": [1, 2]}."""
    ids = (request.get_json(silent=True) or {}).get("ids")
    return _run(lambda db: service.change_errors(db, action, ids))


@superadmin_blueprint.route("/server", methods=["GET"])
@superadmin_required
def get_server():
    """The server's health: load, memory, disk, database size, this container, the bot and the job queue."""
    directory = discord_directory()
    bot_ready = None if directory is None else bool(directory.is_ready())
    return _run(lambda db: service.server(db, bot_ready))


@superadmin_blueprint.route("/server/services", methods=["GET"])
@superadmin_required
def get_server_services():
    """Each container and host process on the server, from the host agent, with its owner."""
    return _run(service.server_services)


@superadmin_blueprint.route("/server/services/<string:name>", methods=["PUT"])
@superadmin_required
def put_server_service(name):
    """Set who owns a service. Body: {"owner": "org", "organization_id": 1}, or {"owner": null} for the labels."""
    body = request.get_json(silent=True)
    actor = _actor()
    return _run(lambda db: service.set_service_owner(db, name, body, actor))


@superadmin_blueprint.route("/server/services/<string:name>/action", methods=["POST"])
@superadmin_required
def server_service_action(name):
    """Start, stop or restart a service on the server, if the runner's policy lists it. Body: {"action": "restart"}."""
    action = (request.get_json(silent=True) or {}).get("action")
    actor = _actor()
    return _run(lambda db: service.service_action(db, name, action, actor))


@superadmin_blueprint.route("/server/services/<string:name>/logs", methods=["GET"])
@superadmin_required
def server_service_logs(name):
    lines = request.args.get("lines", 200, type=int)
    return _run(lambda db: service.service_logs(db, name, lines))


@superadmin_blueprint.route("/limits", methods=["GET"])
@superadmin_required
def get_limits():
    """Every declared limit, and each org's limits, use and overrides."""
    return _run(service.all_limits)


@superadmin_blueprint.route("/limits/<int:org_id>", methods=["GET"])
@superadmin_required
def get_org_limits(org_id):
    """One org's limits, use and overrides."""
    return _run(lambda db: service.org_limits(db, service.find_org(db, org_id)))


@superadmin_blueprint.route("/limits/<int:org_id>", methods=["PUT"])
@superadmin_required
def put_org_limits(org_id):
    """Set an org's limits. Body: {"limits": {"knowledge.sources": 200, "godfather.pods": null}}.

    A number sets the limit, null removes the limit, "default" goes back to the default.
    """
    changes = (request.get_json(silent=True) or {}).get("limits")
    actor = _actor()
    return _run(lambda db: service.set_org_limits(db, service.find_org(db, org_id), changes, actor))


@superadmin_blueprint.route("/submodules", methods=["GET"])
@superadmin_required
def get_submodules():
    """Every submodule with its subscribers, shared pages, passages and failing pages."""
    from modules.submodules import service as submodules

    return _run(lambda db: {"submodules": submodules.overview(db)})


@superadmin_blueprint.route("/shared-apps", methods=["GET"])
@superadmin_required
def list_shared_apps():
    """The shared apps: apps the deployment owns on This server, which orgs subscribe to."""
    return _run(lambda db: {"apps": shared.list_shared(db)})


@superadmin_blueprint.route("/shared-apps/<string:name>", methods=["GET"])
@superadmin_required
def get_shared_app(name):
    """One shared app with its deployments, the names of its secrets and its subscribers."""
    return _run(lambda db: shared.get_shared(db, name))


@superadmin_blueprint.route("/shared-apps/<string:name>", methods=["PUT"])
@superadmin_required
def put_shared_app(name):
    """Register a shared app or replace its manifest. Body: {"manifest": {...}}. It runs on This server."""
    manifest = (request.get_json(silent=True) or {}).get("manifest")
    return _run(lambda db: shared.put_shared(db, name, manifest))


@superadmin_blueprint.route("/shared-apps/<string:name>", methods=["DELETE"])
@superadmin_required
def delete_shared_app(name):
    """Remove a shared app and its container. Its data folders stay on the server."""
    return _run(lambda db: apps.delete_app(db, None, name))


@superadmin_blueprint.route("/shared-apps/<string:name>/deploy", methods=["POST"])
@superadmin_required
def deploy_shared_app(name):
    """Deploy a tag of a shared app. Body: {"tag": "1.2.3", "dry_run": false}."""
    body = request.get_json(silent=True) or {}
    actor = _actor()
    return _run(
        lambda db: (deploys.deploy(db, None, None, name, body.get("tag"), actor, bool(body.get("dry_run"))), 202)
    )


@superadmin_blueprint.route("/shared-apps/<string:name>/rollback", methods=["POST"])
@superadmin_required
def rollback_shared_app(name):
    """Deploy the last healthy tag before the current one."""
    body = request.get_json(silent=True) or {}
    actor = _actor()
    return _run(lambda db: (deploys.rollback(db, None, None, name, actor, bool(body.get("dry_run"))), 202))


@superadmin_blueprint.route("/shared-apps/<string:name>/pod", methods=["GET"])
@superadmin_required
def shared_app_pod(name):
    """The container of a shared app, as the runner describes it."""
    return _run(lambda db: {"pod": apps.pod(db, None, name)})


@superadmin_blueprint.route("/shared-apps/<string:name>/secrets", methods=["PUT"])
@superadmin_required
def put_shared_app_secrets(name):
    """Save secrets of a shared app. Body: {"secrets": {"ADMIN_TOKEN": "...", "OLD_KEY": null}}."""
    values = (request.get_json(silent=True) or {}).get("secrets")
    actor = _actor()
    return _run(lambda db: shared.set_secrets(db, name, values, actor))


@superadmin_blueprint.route("/shared-apps/<string:name>/action", methods=["POST"])
@superadmin_required
def shared_app_action(name):
    """Start, stop or restart a shared app. Body: {"action": "restart"}."""
    action = (request.get_json(silent=True) or {}).get("action")
    return _run(lambda db: apps.app_action(db, None, name, action))


@superadmin_blueprint.route("/shared-apps/<string:name>/logs", methods=["GET"])
@superadmin_required
def shared_app_logs(name):
    lines = request.args.get("lines", 200, type=int)
    return _run(lambda db: apps.app_logs(db, None, name, lines))
