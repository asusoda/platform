import time

from flask import Blueprint, jsonify, request, session

from core import jobs
from core.db import db_connect
from core.http.request_log import bearer_token
from core.log import logger
from modules.auth.access import awarded_by, decide
from modules.auth.decorators import auth_required
from modules.auth.tokens import token_manager
from modules.organizations import service as organizations
from modules.points import service
from modules.points.models import Points
from modules.users import service as users
from modules.users.models import User, UserOrganizationMembership

points_blueprint = Blueprint("points", __name__, template_folder=None, static_folder=None)

LEADERBOARD_CACHE_TTL = 300  # seconds
leaderboard_cache = {}

ORG_NOT_FOUND = "Organization not found"


def _org(db, org_prefix):
    return organizations.find_by_prefix(db, org_prefix, active_only=True)


@points_blueprint.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Points"}), 200


def _clerk_email() -> str | None:
    """The email of the Clerk session token on this request, or None."""
    from modules.auth import clerk

    token = bearer_token()
    if not token:
        return None
    try:
        result = clerk.verify_clerk_token(token)
    except Exception:
        logger.debug("Clerk token verification failed in member_login", exc_info=True)
        return None
    return result[0] if result else None


@points_blueprint.route("/<string:org_prefix>/member_login", methods=["POST"])
def member_login(org_prefix):
    """Link or create the member for the store and keep them in the session."""
    data = request.json

    if not data:
        return jsonify({"error": "Request data is required"}), 400

    # The caller proves the email with a Clerk session token for it
    verified_email = _clerk_email()
    claimed_email = str(data.get("email") or "").strip().lower()
    if not verified_email or verified_email.lower() != claimed_email:
        if decide("member_login_unverified", org=org_prefix):
            return jsonify({"error": "Sign in to log in as this member"}), 403

    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        fields = users.member_input(data)
        user_data = {
            key: fields.get(key) for key in ("name", "username", "email", "student_id", "class_standing", "major")
        }
        user = users.link_or_create_user(organization.id, user_data, session.get("discord_id"))
        if not user:
            return jsonify({"error": "Failed to create or link user account"}), 500

        session["member_user_id"] = user.id
        session["member_org_id"] = organization.id

        return jsonify(
            {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    "asu_id": user.student_id,
                    "discord_linked": bool(user.discord_id),
                },
                "organization": {"id": organization.id, "name": organization.name, "prefix": organization.prefix},
            }
        ), 200

    except Exception as e:
        logger.error(f"Error in getPointsByUser: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving user points"}), 500
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/member_profile", methods=["GET"])
def get_member_profile(org_prefix):
    """The signed-in member's profile, orgs and points."""
    member_user_id = session.get("member_user_id")
    if not member_user_id:
        return jsonify({"error": "Member not logged in"}), 401

    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization

        organization = _org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        user = db.query(User).filter_by(id=member_user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        memberships = db.query(UserOrganizationMembership).filter_by(user_id=user.id, is_active=True).all()

        org_data = []
        total_points_all_orgs = 0
        current_org_points = 0
        current_membership = next((m for m in memberships if m.organization_id == organization.id), None)

        for membership in memberships:
            org = db.query(Organization).filter_by(id=membership.organization_id).first()
            if org:
                org_points = service.total_points(db, user.id, org.id) or 0
                org_data.append(
                    {
                        "id": org.id,
                        "name": org.name,
                        "prefix": org.prefix,
                        "description": org.description,
                        "points": org_points,
                        "is_current": org.id == organization.id,
                    }
                )
                total_points_all_orgs += org_points
                if org.id == organization.id:
                    current_org_points = org_points

        return jsonify(
            {
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    **users.member_fields(user, current_membership),
                    "major": user.major,
                    "discord_linked": bool(user.discord_id),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
                "current_organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "prefix": organization.prefix,
                    "points": current_org_points,
                },
                "organizations": org_data,
                "total_points_all_orgs": total_points_all_orgs,
            }
        ), 200

    except Exception as e:
        logger.error(f"Error in getAllPointsByUser: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving user points across organizations"}), 500
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/users", methods=["POST"])
@auth_required
def manage_user(org_prefix):
    """Create, update or link a member of the org."""
    data = request.json
    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
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
            db, organization.id, user_data, data.get("discord_id"), data.get("user_identifier")
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
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    **users.member_fields(user, membership),
                    "major": user.major,
                    "discord_linked": bool(user.discord_id),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
                "organization": {"name": organization.name, "prefix": organization.prefix},
            }
        ), 201 if "created" in message else 200

    except Exception as e:
        logger.error(f"Error in createOrUpdateUserByOrgPrefix: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while creating or updating user"}), 500
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/add_points", methods=["POST"])
@auth_required
def add_points_to_org(org_prefix):
    """Add points to a member found by Discord id, else by email, uuid or username."""
    data = request.json
    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 400

        user = None
        discord_id = data.get("user_discord_id")
        user_identifier = data.get("user_identifier")

        if not discord_id and not user_identifier:
            return (
                jsonify({"error": "Either 'user_discord_id' or 'user_identifier' must be provided"}),
                400,
            )
        if discord_id:
            user = db.query(User).filter_by(discord_id=discord_id).first()
        if not user and user_identifier:
            user = users.find_by_identifier(db, user_identifier)
        if not user:
            return jsonify({"error": "User does not exist"}), 404

        point = Points(
            points=data["points"],
            user_id=user.id,
            organization_id=organization.id,
            event=data.get("event"),
            awarded_by_officer=awarded_by(data.get("awarded_by_officer")),
        )
        db.add(point)
        db.commit()
        db.refresh(point)

        return jsonify(service.point_json(point)), 201

    except Exception as e:
        db.rollback()
        logger.error(f"Error in addPointsToUserByAsuId: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while adding points"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/users", methods=["GET"])
@auth_required
def get_org_users(org_prefix):
    """The org's active members with their points."""
    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        memberships = (
            db.query(UserOrganizationMembership).filter_by(organization_id=organization.id, is_active=True).all()
        )

        users_data = []
        for membership in memberships:
            user = db.query(User).filter_by(id=membership.user_id).first()
            if user:
                users_data.append(
                    {
                        "id": user.id,
                        "uuid": user.uuid,
                        "name": user.name,
                        "username": user.username,
                        "email": user.email,
                        **users.legacy_member_fields(user),
                        "major": user.major,
                        "discord_linked": bool(user.discord_id),
                        "points": service.total_points(db, user.id, organization.id) or 0,
                        "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                    }
                )

        return jsonify(
            {
                "organization": {
                    "name": organization.name,
                    "prefix": organization.prefix,
                    "description": organization.description,
                },
                "total_users": len(users_data),
                "users": users_data,
            }
        ), 200

    except Exception as e:
        logger.error(f"Error in uploadEventCSV: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while processing CSV upload"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/get_points", methods=["GET"])
@auth_required
def get_org_points(org_prefix):
    """Every point entry in the org."""
    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        points = db.query(Points).filter_by(organization_id=organization.id).all()
        return jsonify([service.point_json(point) for point in points]), 200

    except Exception as e:
        logger.error(f"Error in getAllPointsRecords: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving points records"}), 400
    finally:
        db.close()


def _leaderboard_show_email():
    """(show_email, None), or (None, error response) when the Bearer token is expired or bad."""
    token = bearer_token()
    if not token:
        return False, None
    try:
        if token_manager.is_token_valid(token) and not token_manager.is_token_expired(token):
            return True, None
        if token_manager.is_token_expired(token):
            return None, (jsonify({"message": "Token is expired!"}), 403)
    except Exception as e:
        return None, (jsonify({"message": str(e)}), 401)
    return False, None


@points_blueprint.route("/<string:org_prefix>/leaderboard", methods=["GET"])
def get_org_leaderboard(org_prefix):
    """The org's leaderboard. A valid platform token shows emails; without one it shows uuids."""
    show_email, refusal = _leaderboard_show_email()
    if refusal is not None:
        return refusal

    cache_key = (org_prefix, show_email)
    cache_entry = leaderboard_cache.get(cache_key)
    if cache_entry and time.time() - cache_entry["timestamp"] < LEADERBOARD_CACHE_TTL:
        return jsonify(cache_entry["data"]), 200

    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        response_payload = service.officer_leaderboard(db, organization, bool(show_email))
        leaderboard_cache[cache_key] = {"timestamp": time.time(), "data": response_payload}
        return jsonify(response_payload), 200

    except Exception as e:
        logger.error(f"Error in getLeaderboard: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving leaderboard"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/uploadEventCSV", methods=["POST"])
@auth_required
def upload_event_csv(org_prefix):
    """Queue the points.import_event_csv job for an attendance CSV."""
    if "file" not in request.files or "event_name" not in request.form or "event_points" not in request.form:
        return jsonify({"error": "Missing required fields"}), 400

    file = request.files["file"]
    event_name = request.form["event_name"]
    event_points = int(request.form["event_points"])

    if not file.filename.endswith(".csv"):
        return jsonify({"error": "File must be a CSV"}), 400

    file_content = file.stream.read().decode("utf-8")

    # The job worker runs it, or a thread on SQLite
    jobs.defer(
        "points.import_event_csv",
        file_content=file_content,
        event_name=event_name,
        event_points=event_points,
        org_prefix=org_prefix,
    )

    return jsonify({"message": "File is being processed in the background."}), 202


@points_blueprint.route("/<string:org_prefix>/getUserPoints", methods=["GET"])
@auth_required
def get_user_points_in_org(org_prefix):
    """The point entries of the member with this Discord id in the org."""
    discord_id = request.args.get("discord_id")
    if not discord_id:
        return jsonify({"error": "discord_id parameter is missing"}), 400

    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
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

    except Exception as e:
        logger.error(f"Error in getPointsHistoryByDiscordId: {e}", exc_info=True)
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

    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
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

    except Exception as e:
        logger.error(f"Error in getUserPointsByDiscordId: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving user points"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/assignPoints", methods=["POST"])
@points_blueprint.route("/<string:org_prefix>/assign_points", methods=["POST"])
@auth_required
def assign_points_to_org(org_prefix):
    """Add points to an active member found by email, uuid or username."""
    data = request.json
    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
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

        point = Points(
            points=float(data["points"]),
            user_id=user.id,
            organization_id=organization.id,
            event=data.get("event"),
            awarded_by_officer=awarded_by(data.get("awarded_by_officer")),
        )
        db.add(point)
        db.commit()
        db.refresh(point)

        return jsonify(
            {
                "message": "Points assigned successfully",
                "points": service.point_json(point),
                "user": {"name": user.name, "email": user.email},
                "organization": {"name": organization.name, "prefix": organization.prefix},
            }
        ), 201

    except Exception as e:
        db.rollback()
        logger.error(f"Error in addPointsByDiscordId: {e}", exc_info=True)
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

    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        user = db.query(User).filter_by(email=data["user_email"]).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        points_entry = (
            db.query(Points).filter_by(user_id=user.id, organization_id=organization.id, event=data["event"]).first()
        )
        if not points_entry:
            return jsonify({"error": "Points entry not found"}), 404

        db.delete(points_entry)
        db.commit()

        return jsonify(
            {
                "message": "Points deleted successfully",
                "deleted_points": {
                    "points": points_entry.points,
                    "event": points_entry.event,
                    "timestamp": points_entry.timestamp.isoformat() if points_entry.timestamp else None,
                    "awarded_by_officer": points_entry.awarded_by_officer,
                    "user_id": points_entry.user_id,
                    "organization_id": points_entry.organization_id,
                },
            }
        ), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Error in deletePointsById: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while deleting points"}), 500
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/users/<string:user_identifier>", methods=["PUT", "PATCH"])
@auth_required
def update_user_fields_endpoint(org_prefix, user_identifier):
    """Update the fields sent for an active member. Legacy keys name their columns."""
    data = request.json
    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        user = users.find_by_identifier(db, user_identifier)
        if not user:
            return jsonify({"error": "User not found"}), 404

        membership = users.active_membership(db, user.id, organization.id)
        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 400

        updated_fields = []
        errors = []

        for field_name, field_value in data.items():
            if field_name == "user_identifier":
                continue
            column = users.LEGACY_MEMBER_KEYS.get(field_name, field_name)
            if column != field_name and column in data:
                continue  # the column name sent alongside wins

            if column == "profile_fields":
                error = users.merge_profile_fields(membership, field_value)
                if error:
                    errors.append(f"{field_name}: {error}")
                    continue
                db.commit()
                updated_fields.append(field_name)
                continue

            success, message = users.update_user_field(db, user, column, field_value, organization.id)
            if success:
                updated_fields.append(field_name)
            else:
                errors.append(f"{field_name}: {message}")

        if errors:
            return jsonify({"error": "Some fields failed to update", "details": errors}), 400

        if not updated_fields:
            return jsonify({"message": "No fields to update"}), 200

        return jsonify(
            {
                "message": f"Updated fields: {', '.join(updated_fields)}",
                "updated_fields": updated_fields,
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    **users.member_fields(user, membership),
                    "major": user.major,
                    "discord_linked": bool(user.discord_id),
                },
            }
        ), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Error in updateUserPointsByAsuId: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while updating user points"}), 500
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/users/<string:user_identifier>/points", methods=["GET"])
@auth_required
def get_user_points_in_org_by_identifier(org_prefix, user_identifier):
    """An active member's total and points history in the org."""
    db = next(db_connect.get_db())
    try:
        organization = _org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404

        user = users.find_by_identifier(db, user_identifier)
        if not user:
            return jsonify({"error": "User not found"}), 404

        if not users.active_membership(db, user.id, organization.id):
            return jsonify({"error": "User is not a member of this organization"}), 400

        total_points = service.total_points(db, user.id, organization.id) or 0
        points_records = service.history(db, user.id, organization.id)

        return jsonify(
            {
                "user": {"id": user.id, "name": user.name, "email": user.email, "username": user.username},
                "organization": {"name": organization.name, "prefix": organization.prefix},
                "total_points": total_points,
                "points_history": [service.history_json(record) for record in points_records],
            }
        ), 200

    except Exception as e:
        logger.error(f"Error in getUserPointsByAsuId: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving user points"}), 500
    finally:
        db.close()
