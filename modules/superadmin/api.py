from flask import Blueprint, jsonify, request, session

from core.db import db_connect
from core.log import get_logger
from modules.auth.access import discord_directory
from modules.auth.decorators import superadmin_required
from modules.auth.tokens import token_manager
from modules.organizations.models import Organization

from . import service

logger = get_logger(__name__)

superadmin_blueprint = Blueprint("superadmin", __name__)


@superadmin_blueprint.route("/check", methods=["GET"])
@superadmin_required
def check_superadmin():
    """Whether the caller is the superadmin: 200 when yes, 403 when no."""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.error("Invalid Authorization header format")
            return jsonify({"error": "Authorization header required"}), 401

        token_data = token_manager.decode_token(auth_header.split(" ")[1])
        if not token_data:
            logger.error("Failed to decode token")
            return jsonify({"error": "Invalid token"}), 401

        user_discord_id = token_data.get("discord_id")
        if not user_discord_id:
            logger.error("Token missing Discord ID")
            return jsonify({"error": "Token missing Discord ID"}), 401

        if service.is_superadmin(user_discord_id):
            return jsonify({"is_superadmin": True}), 200
        return jsonify({"is_superadmin": False}), 403
    except Exception as e:
        logger.exception(f"Error in check_superadmin: {e}")
        return jsonify({"error": f"Error checking superadmin status: {str(e)}"}), 500


@superadmin_blueprint.route("/dashboard", methods=["GET"])
@superadmin_required
def get_dashboard():
    """Guilds without an org, every org, and the orgs whose guild has the caller."""
    try:
        directory = discord_directory()
        if directory is None or not directory.is_ready():
            return jsonify({"error": "Bot not available"}), 503

        guilds = directory.list_guilds()
        db = next(db_connect.get_db())
        existing_orgs = db.query(Organization).all()
        officer_id = session.get("user", {}).get("discord_id")
        officer_orgs = service.officer_orgs(directory, existing_orgs, officer_id)

        return jsonify(
            {
                "available_guilds": service.available_guilds(guilds, existing_orgs),
                "existing_orgs": [org.to_dict() for org in existing_orgs],
                "officer_orgs": [org.to_dict() for org in officer_orgs],
            }
        )
    except Exception as e:
        logger.exception(f"Error in get_dashboard: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if "db" in locals():
            db.close()


@superadmin_blueprint.route("/guild_roles/<guild_id>", methods=["GET"])
@superadmin_required
def get_guild_roles(guild_id):
    """The guild's roles, highest first, without @everyone and integration roles."""
    try:
        directory = discord_directory()
        if directory is None or not directory.is_ready():
            return jsonify({"error": "Bot not available"}), 503

        try:
            guild_id_int = int(guild_id)
        except ValueError:
            logger.error(f"Invalid guild ID format: {guild_id}")
            return jsonify({"error": "Invalid guild ID format"}), 400

        guild = directory.get_guild(guild_id_int)
        if not guild:
            logger.error(f"Guild not found for ID: {guild_id_int}")
            return jsonify({"error": "Guild not found"}), 404

        return jsonify({"roles": service.guild_roles(directory, guild_id_int)})
    except Exception as e:
        logger.exception(f"Error in get_guild_roles: {e}")
        return jsonify({"error": str(e)}), 500


@superadmin_blueprint.route("/update_officer_role/<int:org_id>", methods=["PUT"])
@superadmin_required
def update_officer_role(org_id):
    """Set the org's officer role. An empty officer_role_id clears it."""
    try:
        data = request.get_json()
        if not data or "officer_role_id" not in data:
            logger.error("Missing officer_role_id in request data")
            return jsonify({"error": "officer_role_id is required"}), 400

        officer_role_id = data["officer_role_id"]

        directory = discord_directory()
        if directory is None or not directory.is_ready():
            return jsonify({"error": "Bot not available"}), 503

        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id).first()

        if not org:
            logger.error(f"Organization not found for ID: {org_id}")
            return jsonify({"error": "Organization not found"}), 404

        try:
            guild = directory.get_guild(int(org.guild_id))
            if not guild:
                logger.error(f"Guild not found for ID: {org.guild_id}")
                return jsonify({"error": "Guild not found"}), 404

            if officer_role_id and not service.role_in_guild(directory, org.guild_id, officer_role_id):
                logger.error(f"Role not found in guild for ID: {officer_role_id}")
                return jsonify({"error": "Role not found in guild"}), 404

        except (ValueError, AttributeError) as e:
            logger.error(f"Error verifying role: {e}")
            return jsonify({"error": f"Invalid role ID format: {str(e)}"}), 400

        org.officer_role_id = officer_role_id
        db.commit()

        return jsonify({"message": f"Officer role updated successfully for {org.name}", "organization": org.to_dict()})
    except Exception as e:
        logger.exception(f"Error in update_officer_role: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if "db" in locals():
            db.close()


@superadmin_blueprint.route("/add_org/<guild_id>", methods=["POST"])
@superadmin_required
def add_organization(guild_id):
    """Add an org for a guild the bot is in, with default settings."""
    try:
        directory = discord_directory()
        if directory is None or not directory.is_ready():
            return jsonify({"error": "Bot not available"}), 503

        try:
            guild_id_int = int(guild_id)
        except ValueError:
            return jsonify({"error": "Invalid guild ID format"}), 400

        guild = directory.get_guild(guild_id_int)
        if not guild:
            return jsonify({"error": "Guild not found"}), 404

        new_org = service.new_organization(guild)

        db = next(db_connect.get_db())
        db.add(new_org)
        db.commit()

        return jsonify({"message": f"Organization {guild['name']} added successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@superadmin_blueprint.route("/remove_org/<int:org_id>", methods=["DELETE"])
@superadmin_required
def remove_organization(org_id):
    """Delete an org."""
    try:
        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id).first()

        if not org:
            return jsonify({"error": "Organization not found"}), 404

        org_name = org.name
        db.delete(org)
        db.commit()

        return jsonify({"message": f"Organization {org_name} removed successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@superadmin_blueprint.route("/audit", methods=["GET"])
@superadmin_required
def get_audit():
    """Audit log across all orgs, newest first. ?org=<prefix>&limit=100&before_id=<id>."""
    from core import audit

    db = next(db_connect.get_db())
    try:
        entries = audit.list_entries(
            db,
            org=request.args.get("org"),
            limit=request.args.get("limit", 100, type=int),
            before_id=request.args.get("before_id", type=int),
        )
        return jsonify({"entries": entries})
    finally:
        db.close()
