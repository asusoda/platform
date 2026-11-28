"""Officer routes of points: members, point entries, awards and the attendance CSV imports.

The member and public routes (store sign-in, member profile, leaderboard) are in member_api.py.
"""

from flask import Blueprint, jsonify, request

from core.db import db_connect
from core.http.cached import cached_json, org_key
from core.log import get_logger
from modules.auth.access import awarded_by, is_org_officer
from modules.auth.decorators import auth_required
from modules.auth.routes import officer_route
from modules.members import service as users
from modules.members.models import User, UserOrganizationMembership
from modules.organizations import service as organizations
from modules.points import csv_import, service
from modules.points.models import Points

logger = get_logger(__name__)

points_blueprint = Blueprint("points", __name__, template_folder=None, static_folder=None)

# Writes in this process drop the officer lists at once; writes elsewhere drop them through core.cache.publish
OFFICER_LIST_TTL = 30  # seconds
MAX_CSV_BYTES = 2_000_000

ORG_NOT_FOUND = "Organization not found"


def active_org(db, org_prefix):
    return organizations.find_by_prefix(db, org_prefix, active_only=True)


@points_blueprint.route("/<string:org_prefix>/users", methods=["POST"])
@auth_required
def manage_user(org_prefix):
    """Create, update or link a member of the org."""
    data = request.json
    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        fields = users.member_input(data)
        user_data = {
            key: fields.get(key)
            for key in ("username", "email", "name", "student_id", "class_standing", "major", "profile_fields")
        }
        # A missing field keeps the stored value
        user_data = {k: v for k, v in user_data.items() if v is not None}

        user, success, message = users.manage_user_in_organization(
            db, organization.id, user_data, data.get("discord_id"), data.get("user_identifier"), by_officer=True
        )
        if not success:
            return jsonify({"error": message}), 400

        membership = (
            db.query(UserOrganizationMembership).filter_by(user_id=user.id, organization_id=organization.id).first()
        )
        return jsonify(
            {
                "message": message,
                "user": {
                    **service.member_json(user, membership),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
                "organization": {"name": organization.name, "prefix": organization.prefix},
            }
        ), 201 if "created" in message else 200
    except Exception:
        logger.exception("member save failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while creating or updating user"}), 500
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/add_points", methods=["POST"])
@auth_required
def add_points_to_org(org_prefix):
    """Add points to a member found by Discord id, else by email, uuid or username."""
    data = request.json
    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 400

        discord_id = data.get("user_discord_id")
        user_identifier = data.get("user_identifier")
        if not discord_id and not user_identifier:
            return jsonify({"error": "Either 'user_discord_id' or 'user_identifier' must be provided"}), 400
        user = db.query(User).filter_by(discord_id=discord_id).first() if discord_id else None
        if not user and user_identifier:
            user = users.find_by_identifier(db, user_identifier)
        if not user:
            return jsonify({"error": "User does not exist"}), 404

        point = service.add_entry(
            db, organization.id, user, data["points"], data.get("event"), awarded_by(data.get("awarded_by_officer"))
        )
        return jsonify(service.point_json(point)), 201
    except Exception:
        db.rollback()
        logger.exception("add_points failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while adding points"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/users", methods=["GET"])
@auth_required
def get_org_users(org_prefix):
    """The org's active members with their points."""
    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        organization_id = organization.id
        organization_json = {
            "name": organization.name,
            "prefix": organization.prefix,
            "description": organization.description,
        }

        def build():
            users_data = service.members_with_points(db, organization_id)
            return {"organization": organization_json, "total_users": len(users_data), "users": users_data}

        return cached_json(org_key(org_prefix, "points", "users"), OFFICER_LIST_TTL, build)
    except Exception:
        logger.exception("member list failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while retrieving the members"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/get_points", methods=["GET"])
@auth_required
def get_org_points(org_prefix):
    """Every point entry in the org."""
    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        organization_id = organization.id

        def build():
            points = db.query(Points).filter_by(organization_id=organization_id).order_by(Points.id).all()
            return [service.point_json(point) for point in points]

        return cached_json(org_key(org_prefix, "points", "entries"), OFFICER_LIST_TTL, build)
    except Exception:
        logger.exception("point entries failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while retrieving points records"}), 400
    finally:
        db.close()


def _event_points(value: str) -> int:
    """The points of a CSV upload as a whole number. Raises PointsError 400 for any other value."""
    try:
        return int(value.strip())
    except (AttributeError, ValueError):
        raise service.PointsError("event_points must be a whole number") from None


@officer_route(points_blueprint, "/uploadEventCSV", ["POST"])
def upload_event_csv(db, org):
    """Add a CSV import run and queue the points.import_event_csv job for it. 202 with the run's id."""
    if "file" not in request.files or "event_name" not in request.form or "event_points" not in request.form:
        return {"error": "Missing required fields"}, 400
    file = request.files["file"]
    event_points = _event_points(request.form["event_points"])
    if not file.filename or not file.filename.endswith(".csv"):
        return {"error": "File must be a CSV"}, 400
    raw = file.stream.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        return {"error": "The CSV is larger than 2 MB"}, 413
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"error": "The CSV must be UTF-8 text"}, 400

    run = csv_import.queue(db, org, content, request.form["event_name"], event_points, awarded_by(None))
    return {"message": "File is being processed in the background.", "import_id": run.id}, 202


@officer_route(points_blueprint, "/imports", ["GET"])
def list_imports(db, org):
    """The org's newest 20 CSV import runs."""
    return {"imports": csv_import.runs(db, org.id)}


@officer_route(points_blueprint, "/imports/<int:import_id>", ["GET"])
def get_import(db, org, import_id):
    """One CSV import run of the org, with its progress and row errors."""
    run = csv_import.run(db, org.id, import_id)
    if run is None:
        return {"error": "Import not found"}, 404
    return csv_import.run_json(run)


@points_blueprint.route("/<string:org_prefix>/getUserPoints", methods=["GET"])
@auth_required
def get_user_points_in_org(org_prefix):
    """The point entries of the member with this Discord id in the org."""
    discord_id = request.args.get("discord_id")
    if not discord_id:
        return jsonify({"error": "discord_id parameter is missing"}), 400

    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        user = db.query(User).filter_by(discord_id=discord_id).first()
        if not user:
            return jsonify({"error": "User does not exist"}), 404

        points_records = db.query(Points).filter_by(user_id=user.id, organization_id=organization.id).all()
        if not points_records:
            return jsonify({"message": "No points earned by this user in this organization"}), 200

        return jsonify(
            [{**service.history_json(record), "organization_id": record.organization_id} for record in points_records]
        ), 200
    except Exception:
        logger.exception("points history by Discord id failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while retrieving points history"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/getUserTotalPoints", methods=["GET"])
@auth_required
def get_user_total_points_in_org(org_prefix):
    """The total points of the member with this Discord id in the org."""
    discord_id = request.args.get("discord_id")
    if not discord_id:
        return jsonify({"error": "discord_id parameter is missing"}), 400

    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        user = db.query(User).filter_by(discord_id=discord_id).first()
        if not user:
            return jsonify({"error": "User does not exist"}), 404

        return jsonify(
            {
                "user_id": user.id,
                "discord_id": user.discord_id,
                "username": user.username,
                "organization_id": organization.id,
                "total_points": service.total_points(db, user.id, organization.id) or 0.0,
            }
        ), 200
    except Exception:
        logger.exception("total points by Discord id failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while retrieving user points"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/assignPoints", methods=["POST"])
@points_blueprint.route("/<string:org_prefix>/assign_points", methods=["POST"])
@auth_required
def assign_points_to_org(org_prefix):
    """Add points to an active member found by email, uuid or username."""
    data = request.json
    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        if not data.get("user_identifier"):
            return jsonify({"error": "user_identifier is required"}), 400
        if not data.get("points"):
            return jsonify({"error": "points is required"}), 400

        user = users.find_by_identifier(db, data["user_identifier"])
        if not user:
            return jsonify({"error": "User not found"}), 404
        if not users.active_membership(db, user.id, organization.id):
            return jsonify({"error": "User is not a member of this organization"}), 400

        point = service.add_entry(
            db,
            organization.id,
            user,
            float(data["points"]),
            data.get("event"),
            awarded_by(data.get("awarded_by_officer")),
        )
        return jsonify(
            {
                "message": "Points assigned successfully",
                "points": service.point_json(point),
                "user": {"name": user.name, "email": user.email},
                "organization": {"name": organization.name, "prefix": organization.prefix},
            }
        ), 201
    except Exception:
        db.rollback()
        logger.exception("assign_points failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while adding points"}), 500
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/delete_points", methods=["DELETE"])
@auth_required
def delete_points_by_event(org_prefix):
    """Delete a member's first entry for an event in the org."""
    data = request.json
    if not data or "user_email" not in data or "event" not in data:
        return jsonify({"error": "user_email and event are required"}), 400

    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404
        try:
            entry = service.delete_event_entry(db, organization.id, data["user_email"], data["event"])
        except service.PointsError as e:
            return jsonify({"error": e.message}), e.status

        return jsonify(
            {
                "message": "Points deleted successfully",
                "deleted_points": {
                    "points": entry.points,
                    "event": entry.event,
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    "awarded_by_officer": entry.awarded_by_officer,
                    "user_id": entry.user_id,
                    "organization_id": entry.organization_id,
                },
            }
        ), 200
    except Exception:
        db.rollback()
        logger.exception("delete_points failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while deleting points"}), 500
    finally:
        db.close()


@officer_route(points_blueprint, "/entries/<int:entry_id>", ["DELETE"])
def delete_entry(db, org, entry_id):
    """Delete one point entry of the org by its id. An entry of another org is not found."""
    return {"message": "Points deleted successfully", "deleted_points": service.delete_entry(db, org.id, entry_id)}


@points_blueprint.route("/<string:org_prefix>/users/<string:user_identifier>", methods=["PUT", "PATCH"])
@auth_required
def update_user_fields_endpoint(org_prefix, user_identifier):
    """Update the fields sent for an active member. Legacy keys name their columns."""
    data = request.json
    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404
        try:
            result = users.update_member(db, organization.id, user_identifier, data)
        except users.MemberError as e:
            return jsonify({"error": e.message}), e.status
        user, membership = result["user"], result["membership"]
        updated_fields, errors = result["updated_fields"], result["errors"]

        if errors:
            return jsonify({"error": "Some fields failed to update", "details": errors}), 400
        if not updated_fields:
            return jsonify({"message": "No fields to update"}), 200
        return jsonify(
            {
                "message": f"Updated fields: {', '.join(updated_fields)}",
                "updated_fields": updated_fields,
                "user": service.member_json(user, membership),
            }
        ), 200
    except Exception:
        db.rollback()
        logger.exception("member update failed org=%s member=%s", org_prefix, user_identifier)
        return jsonify({"error": "An error occurred while updating user points"}), 500
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/users/<string:user_identifier>/points", methods=["GET"])
@auth_required
def get_user_points_in_org_by_identifier(org_prefix, user_identifier):
    """An active member's total and points history in the org."""
    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        user = users.find_by_identifier(db, user_identifier)
        if not user:
            return jsonify({"error": "User not found"}), 404
        membership = users.active_membership(db, user.id, organization.id)
        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 400

        # Student ids and profile fields only go to the org's officers, also while ACCESS_ENFORCE is off
        details = {**users.member_fields(user, membership), "major": user.major} if is_org_officer(organization) else {}
        return jsonify(
            {
                "user": {"id": user.id, "name": user.name, "email": user.email, "username": user.username, **details},
                "organization": {"name": organization.name, "prefix": organization.prefix},
                "total_points": service.total_points(db, user.id, organization.id) or 0,
                "points_history": [service.history_json(r) for r in service.history(db, user.id, organization.id)],
            }
        ), 200
    except Exception:
        logger.exception("member points failed org=%s member=%s", org_prefix, user_identifier)
        return jsonify({"error": "An error occurred while retrieving user points"}), 500
    finally:
        db.close()
