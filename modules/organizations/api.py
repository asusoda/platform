import logging
import re

from flask import Blueprint, jsonify, request

from core.db import db_connect
from modules.auth.access import visible_org_filter
from modules.auth.decoraters import auth_required
from modules.organizations import service
from modules.organizations.models import Organization

organizations_blueprint = Blueprint("organizations", __name__)


@organizations_blueprint.route("/", methods=["GET"])
@auth_required
def get_organizations():
    """Get all organizations the user has access to"""
    try:
        db = next(db_connect.get_db())
        organizations = db.query(Organization).filter_by(is_active=True).order_by(Organization.id).all()
        visible = visible_org_filter()
        if visible is not None:
            organizations = [org for org in organizations if str(org.guild_id) in visible]

        return jsonify([org.to_dict() for org in organizations])
    except Exception:
        logging.exception("Error while fetching organizations")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>", methods=["GET"])
@auth_required
def get_organization(org_id):
    """Get specific organization details"""
    try:
        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()

        if not org:
            return jsonify({"error": "Organization not found"}), 404

        return jsonify(org.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/stats", methods=["GET"])
@auth_required
def get_organization_stats(org_id):
    """Get organization statistics"""
    try:
        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()

        if not org:
            return jsonify({"error": "Organization not found"}), 404

        # Return mock stats for now - implement actual stats logic later
        stats = {"totalMembers": 25, "totalPoints": 1250, "activeEvents": 3, "monthlyPoints": 340}

        return jsonify(stats)
    except Exception:
        logging.exception("Error while fetching organization stats for org_id=%s", org_id)
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/activity", methods=["GET"])
@auth_required
def get_organization_activity(org_id):
    """Get recent organization activity"""
    try:
        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()

        if not org:
            return jsonify({"error": "Organization not found"}), 404

        # Return mock activity for now - implement actual activity logic later
        activity = [
            {
                "user_name": "John Doe",
                "description": "Attended weekly meeting",
                "points": 10,
                "timestamp": "2025-07-24T12:00:00Z",
            },
            {
                "user_name": "Jane Smith",
                "description": "Completed project milestone",
                "points": 25,
                "timestamp": "2025-07-23T15:30:00Z",
            },
        ]

        return jsonify(activity)
    except Exception:
        logging.exception("Error while fetching organization activity for org_id=%s", org_id)
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/settings", methods=["PUT"])
@auth_required
def update_organization_settings(org_id):
    """Update organization settings"""
    try:
        data = request.get_json()
        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()

        if not org:
            return jsonify({"error": "Organization not found"}), 404

        # Update organization settings
        if "config" in data:
            # Module switches and LeetCode settings have their own routes; keep them when the rest is replaced
            kept = {k: v for k, v in (org.config or {}).items() if k in ("modules", "leetcode")}
            org.config = data["config"]
            if isinstance(org.config, dict):
                org.config = {**kept, **org.config}
        if "prefix" in data:
            new_prefix = data["prefix"].strip()

            # Validate prefix format
            if not new_prefix or len(new_prefix) < 2:
                return jsonify({"error": "Prefix must be at least 2 characters"}), 400
            if len(new_prefix) > 20:
                return jsonify({"error": "Prefix must be 20 characters or less"}), 400
            if not re.match(r"^[a-z0-9_-]+$", new_prefix):
                return jsonify(
                    {"error": "Prefix can only contain lowercase letters, numbers, hyphens, and underscores"}
                ), 400

            # Check if prefix is already taken by another organization
            existing_org = db.query(Organization).filter_by(prefix=new_prefix).first()
            if existing_org and existing_org.id != org_id:
                return jsonify({"error": "Prefix is already taken by another organization"}), 400

            org.prefix = new_prefix
        if "description" in data:
            org.description = data["description"]
        if "officer_role_id" in data:
            org.officer_role_id = data["officer_role_id"]
        if "points_per_message" in data:
            org.points_per_message = data["points_per_message"]
        if "points_cooldown" in data:
            org.points_cooldown = data["points_cooldown"]

        db.commit()
        return jsonify({"message": "Settings updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/calendar", methods=["PUT"])
@auth_required
def update_organization_calendar_settings(org_id):
    """Update organization calendar settings"""
    try:
        data = request.get_json()
        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()

        if not org:
            return jsonify({"error": "Organization not found"}), 404

        # Update calendar-related settings
        if "notion_database_id" in data:
            org.notion_database_id = data["notion_database_id"].strip() if data["notion_database_id"] else None
        if "calendar_sync_enabled" in data:
            org.calendar_sync_enabled = bool(data["calendar_sync_enabled"])
        if "google_calendar_id" in data:
            org.google_calendar_id = data["google_calendar_id"].strip() if data["google_calendar_id"] else None

        db.commit()
        return jsonify({"message": "Calendar settings updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/calendar", methods=["GET"])
@auth_required
def get_organization_calendar_settings(org_id):
    """Get organization calendar settings"""
    try:
        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()

        if not org:
            return jsonify({"error": "Organization not found"}), 404

        calendar_settings = {
            "notion_database_id": org.notion_database_id,
            "calendar_sync_enabled": org.calendar_sync_enabled,
            "google_calendar_id": org.google_calendar_id,
            "last_sync_at": org.last_sync_at.isoformat() if org.last_sync_at else None,
        }

        return jsonify(calendar_settings)
    except Exception:
        logging.exception("Error while fetching organization calendar settings for org_id=%s", org_id)
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/roles", methods=["GET"])
@auth_required
def get_organization_roles(org_id):
    """Get Discord roles for the organization"""
    try:
        # Return mock roles for now - implement actual Discord role fetching later
        roles = [
            {"id": "123456789", "name": "Officer"},
            {"id": "987654321", "name": "Member"},
            {"id": "456789123", "name": "Admin"},
        ]

        return jsonify(roles)
    except Exception:
        logging.exception("Error while fetching organization roles for org_id=%s", org_id)
        return jsonify({"error": "Internal server error"}), 500


@organizations_blueprint.route("/<int:org_id>/modules", methods=["GET"])
@auth_required
def get_organization_modules(org_id):
    """Which optional modules are on for this organization."""
    db = next(db_connect.get_db())
    try:
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
        return jsonify({"modules": service.module_states(org)})
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/modules", methods=["PUT"])
@auth_required
def update_organization_modules(org_id):
    """Turn optional modules on or off. Body: {"modules": {"storefront": false}}."""
    data = request.get_json(silent=True) or {}
    db = next(db_connect.get_db())
    try:
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
        try:
            states = service.set_modules(db, org, data.get("modules"))
        except service.ModuleError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"modules": states})
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/leetcode", methods=["GET"])
@auth_required
def get_organization_leetcode(org_id):
    """The org's daily LeetCode post settings."""
    from modules.leetcode import service as leetcode

    db = next(db_connect.get_db())
    try:
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
        return jsonify({"settings": leetcode.settings(org), "enabled": service.module_enabled(org, "leetcode")})
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/leetcode", methods=["PUT"])
@auth_required
def update_organization_leetcode(org_id):
    """Change the daily post settings. Body: {"channel_id": "...", "role_ping": "...", "daily_time": "09:00"}."""
    from modules.leetcode import service as leetcode

    data = request.get_json(silent=True)
    db = next(db_connect.get_db())
    try:
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
        try:
            saved = leetcode.save_settings(db, org, data)
        except leetcode.SettingsError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"settings": saved, "enabled": service.module_enabled(org, "leetcode")})
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/audit", methods=["GET"])
@auth_required
def get_organization_audit(org_id):
    """Recent changes in this organization, newest first. ?limit=100&before_id=<id> to page."""
    from core import audit

    db = next(db_connect.get_db())
    try:
        org = db.query(Organization).filter_by(id=org_id, is_active=True).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
        entries = audit.list_entries(
            db,
            org=org.prefix,
            limit=request.args.get("limit", 100, type=int),
            before_id=request.args.get("before_id", type=int),
        )
        return jsonify({"entries": entries})
    finally:
        db.close()


def _active_org(db, org_id):
    return db.query(Organization).filter_by(id=org_id, is_active=True).first()


@organizations_blueprint.route("/<int:org_id>/secrets", methods=["GET"])
@auth_required
def list_organization_secrets(org_id):
    """Which secrets this org has saved. Values are never returned."""
    from core import secrets

    db = next(db_connect.get_db())
    try:
        if not _active_org(db, org_id):
            return jsonify({"error": "Organization not found"}), 404
        return jsonify({"configured": secrets.configured(), "secrets": secrets.list_secrets(db, org_id)})
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/secrets/<string:name>", methods=["PUT"])
@auth_required
def set_organization_secret(org_id, name):
    """Save a secret. Body: {"value": "..."}."""
    from core import secrets
    from modules.auth.access import current_principal

    data = request.get_json(silent=True) or {}
    db = next(db_connect.get_db())
    try:
        if not _active_org(db, org_id):
            return jsonify({"error": "Organization not found"}), 404
        principal = current_principal()
        try:
            secrets.set_secret(db, org_id, name, data.get("value"), principal.discord_id if principal else None)
        except secrets.SecretsError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"name": name, "set": True})
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/secrets/<string:name>", methods=["DELETE"])
@auth_required
def delete_organization_secret(org_id, name):
    from core import secrets

    db = next(db_connect.get_db())
    try:
        if not _active_org(db, org_id):
            return jsonify({"error": "Organization not found"}), 404
        if not secrets.delete_secret(db, org_id, name):
            return jsonify({"error": "Secret not set"}), 404
        return jsonify({"name": name, "set": False})
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/tokens", methods=["GET"])
@auth_required
def list_machine_tokens(org_id):
    """Active machine tokens for this org, and the scopes a token can hold."""
    from modules.auth import machine_tokens
    from modules.auth.scopes import SCOPES

    db = next(db_connect.get_db())
    try:
        if not _active_org(db, org_id):
            return jsonify({"error": "Organization not found"}), 404
        return jsonify({"tokens": machine_tokens.list_active(db, org_id), "scopes": SCOPES})
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/tokens", methods=["POST"])
@auth_required
def create_machine_token(org_id):
    """Issue a token. Body: {"name", "kind": app|agent|cli, "scopes": [...], "expires_days"?}.
    The token value is in this response only."""
    from modules.auth import machine_tokens
    from modules.auth.access import current_principal

    data = request.get_json(silent=True) or {}
    db = next(db_connect.get_db())
    try:
        if not _active_org(db, org_id):
            return jsonify({"error": "Organization not found"}), 404
        principal = current_principal()
        try:
            value, row = machine_tokens.issue(
                db,
                organization_id=org_id,
                name=data.get("name"),
                kind=data.get("kind"),
                scopes=data.get("scopes"),
                created_by=principal.discord_id if principal else None,
                expires_days=data.get("expires_days"),
            )
        except machine_tokens.TokenError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"token": value, **machine_tokens.to_dict(row)}), 201
    finally:
        db.close()


@organizations_blueprint.route("/<int:org_id>/tokens/<int:token_id>", methods=["DELETE"])
@auth_required
def revoke_machine_token(org_id, token_id):
    from modules.auth import machine_tokens

    db = next(db_connect.get_db())
    try:
        if not machine_tokens.revoke(db, org_id, token_id):
            return jsonify({"error": "Token not found"}), 404
        return jsonify({"message": "Token revoked"})
    finally:
        db.close()
