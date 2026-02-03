import logging

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from modules.auth.decoraters import auth_required, error_handler
from modules.points.models import Points, User
from shared import db_connect

logger = logging.getLogger(__name__)

# Flask Blueprint for users
users_blueprint = Blueprint("users", __name__, template_folder=None, static_folder=None)


@users_blueprint.route("/", methods=["GET"])
def users_index():
    return jsonify({"message": "users api"}), 200


@users_blueprint.route("/<string:org_prefix>/viewUser", methods=["GET"])
@auth_required
@error_handler
def view_user_in_org(org_prefix):
    # Get the user identifier from query parameters
    user_identifier = request.args.get("user_identifier")
    request.args.get("organization_id")

    if not user_identifier:
        return jsonify({"error": "User identifier (email, UUID, or username) is required."}), 400

    db = next(db_connect.get_db())

    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Query the user by email, UUID, or username
        user = (
            db.query(User)
            .filter(
                (User.email == user_identifier) | (User.uuid == user_identifier) | (User.username == user_identifier)
            )
            .first()
        )

        if not user:
            return jsonify({"error": "User not found."}), 404

        # Check if user is a member of this organization
        membership = (
            db.query(UserOrganizationMembership)
            .filter_by(user_id=user.id, organization_id=organization.id, is_active=True)
            .first()
        )

        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 404

        # Get user's points in this organization
        org_points = (
            db.query(func.sum(Points.points)).filter_by(user_id=user.id, organization_id=organization.id).scalar() or 0
        )

        # Get points records for this organization
        points_records = (
            db.query(Points)
            .filter_by(user_id=user.id, organization_id=organization.id)
            .order_by(Points.last_updated.desc())
            .all()
        )

        points_data = [
            {
                "id": record.id,
                "points": record.points,
                "event": record.event,
                "awarded_by_officer": record.awarded_by_officer,
                "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                "last_updated": record.last_updated.isoformat() if record.last_updated else None,
            }
            for record in points_records
        ]

        # Prepare the user data
        user_data = {
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "email": user.email,
            "uuid": user.uuid,
            "asu_id": user.asu_id,
            "academic_standing": user.academic_standing,
            "major": user.major,
            "discord_linked": bool(user.discord_id),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "points": org_points,
            "points_history": points_data,
            "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "prefix": organization.prefix,
                "description": organization.description,
            },
        }

        return jsonify(user_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/createUser", methods=["POST"])
@auth_required
@error_handler
def create_user_in_org(org_prefix):
    user_email = request.args.get("email")
    user_name = request.args.get("name")
    user_asu_id = request.args.get("asu_id")
    user_academic_standing = request.args.get("academic_standing")

    if not user_email or not user_name:
        return jsonify({"error": "Email and name are required"}), 400

    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Check if user already exists
        existing_user = db.query(User).filter_by(email=user_email).first()

        if existing_user:
            # Check if user is already a member of this organization
            membership = (
                db.query(UserOrganizationMembership)
                .filter_by(user_id=existing_user.id, organization_id=organization.id, is_active=True)
                .first()
            )

            if membership:
                return jsonify({"error": "User is already a member of this organization"}), 400

            # Add existing user to this organization
            new_membership = UserOrganizationMembership(user_id=existing_user.id, organization_id=organization.id)
            db.add(new_membership)
            db.commit()
            return jsonify({"message": "Existing user added to organization successfully."}), 200

        # Create new user
        import uuid

        new_user = User(
            email=user_email,
            name=user_name,
            username=None,  # Can be set later
            asu_id=user_asu_id if user_asu_id and user_asu_id != "N/A" else None,
            academic_standing=user_academic_standing or "N/A",
            major="N/A",
            uuid=str(uuid.uuid4()),
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Add membership to organization
        membership = UserOrganizationMembership(user_id=new_user.id, organization_id=organization.id)
        db.add(membership)
        db.commit()

        return jsonify({"message": "User created and added to organization successfully."}), 201

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/user", methods=["GET", "POST"])
@auth_required
@error_handler
def user_in_org(org_prefix):
    # Get the user email from query parameters for GET request or from POST data
    user_email = request.args.get("email") if request.method == "GET" else request.json.get("email")

    if not user_email:
        return jsonify({"error": "Email is required."}), 400

    db = next(db_connect.get_db())

    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Query the user by email
        user = db.query(User).filter_by(email=user_email).first()

        # Handle GET request - return user info if found
        if request.method == "GET":
            if not user:
                return jsonify({"error": "User not found."}), 404

            # Check if user is a member of this organization
            membership = (
                db.query(UserOrganizationMembership)
                .filter_by(user_id=user.id, organization_id=organization.id, is_active=True)
                .first()
            )

            if not membership:
                return jsonify({"error": "User is not a member of this organization"}), 404

            user_data = {
                "name": user.name,
                "email": user.email,
                "uuid": user.uuid,
                "asu_id": user.asu_id,
                "academic_standing": user.academic_standing,
                "major": user.major,
            }
            return jsonify(user_data), 200

        # Handle POST request - update user info or create a new user if not found
        elif request.method == "POST":
            data = request.json

            if user:
                # Check if user is a member of this organization
                membership = (
                    db.query(UserOrganizationMembership)
                    .filter_by(user_id=user.id, organization_id=organization.id, is_active=True)
                    .first()
                )

                if not membership:
                    return jsonify({"error": "User is not a member of this organization"}), 404

                # Update user fields only if they are provided
                if "name" in data:
                    user.name = data["name"]
                if "asu_id" in data:
                    user.asu_id = data["asu_id"]
                if "academic_standing" in data:
                    user.academic_standing = data["academic_standing"]
                if "major" in data:
                    user.major = data["major"]

                db.commit()
                return jsonify({"message": "User information updated successfully."}), 200

            else:
                # Create a new user if not found
                import uuid

                new_user = User(
                    name=data.get("name"),
                    email=user_email,
                    username=None,  # Can be set later
                    asu_id=data.get("asu_id") if data.get("asu_id") and data.get("asu_id") != "N/A" else None,
                    academic_standing=data.get("academic_standing", "N/A"),
                    major=data.get("major", "N/A"),
                    uuid=str(uuid.uuid4()),
                )

                db.add(new_user)
                db.commit()
                db.refresh(new_user)

                # Add membership to organization
                membership = UserOrganizationMembership(user_id=new_user.id, organization_id=organization.id)
                db.add(membership)
                db.commit()

                return jsonify({"message": "User created and added to organization successfully."}), 201

    except Exception as e:
        db.rollback()  # Rollback in case of any error
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/submit-form", methods=["POST"])
def handle_form_submission_in_org(org_prefix):
    try:
        # Get the JSON data from the POST request
        data = request.get_json()

        # Extract full name and role from the form submission
        discordID = data.get("discordID")
        role = data.get("role")

    except Exception:
        logger.exception("Error while handling form submission for org_prefix=%s", org_prefix)
        return jsonify({"error": "An internal error occurred while processing the form."}), 500

    return jsonify({"message": "recieved id: " + discordID + " and role: " + role}), 200


@users_blueprint.route("/<string:org_prefix>/users", methods=["GET"])
@auth_required
@error_handler
def get_organization_users(org_prefix):
    """Get all users for a specific organization"""
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Get all users who are members of this organization
        memberships = (
            db.query(UserOrganizationMembership).filter_by(organization_id=organization.id, is_active=True).all()
        )

        users_data = []
        for membership in memberships:
            user = db.query(User).filter_by(id=membership.user_id).first()
            if user:
                # Get user's points in this organization
                user_points = (
                    db.query(func.sum(Points.points))
                    .filter_by(user_id=user.id, organization_id=organization.id)
                    .scalar()
                    or 0
                )

                users_data.append(
                    {
                        "id": user.id,
                        "name": user.name,
                        "username": user.username,
                        "email": user.email,
                        "asu_id": user.asu_id,
                        "academic_standing": user.academic_standing,
                        "major": user.major,
                        "discord_linked": bool(user.discord_id),
                        "points": user_points,
                        "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                    }
                )

        return jsonify(
            {
                "organization": {
                    "name": organization.name,
                    "prefix": organization.prefix,
                    "description": organization.description,
                },
                "total_members": len(users_data),
                "users": users_data,
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/users/<string:user_identifier>", methods=["GET"])
@auth_required
@error_handler
def get_user_in_organization(org_prefix, user_identifier):
    """Get a specific user's details within an organization"""
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Find user by email, UUID, or username
        user = (
            db.query(User)
            .filter(
                (User.email == user_identifier) | (User.uuid == user_identifier) | (User.username == user_identifier)
            )
            .first()
        )

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Check if user is a member of this organization
        membership = (
            db.query(UserOrganizationMembership)
            .filter_by(user_id=user.id, organization_id=organization.id, is_active=True)
            .first()
        )

        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 404

        # Get user's points in this organization
        user_points = (
            db.query(func.sum(Points.points)).filter_by(user_id=user.id, organization_id=organization.id).scalar() or 0
        )

        # Get points history for this organization
        points_records = (
            db.query(Points)
            .filter_by(user_id=user.id, organization_id=organization.id)
            .order_by(Points.last_updated.desc())
            .all()
        )

        points_history = [
            {
                "id": record.id,
                "points": record.points,
                "event": record.event,
                "awarded_by_officer": record.awarded_by_officer,
                "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                "last_updated": record.last_updated.isoformat() if record.last_updated else None,
            }
            for record in points_records
        ]

        return jsonify(
            {
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    "asu_id": user.asu_id,
                    "academic_standing": user.academic_standing,
                    "major": user.major,
                    "discord_linked": bool(user.discord_id),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
                "organization": {
                    "name": organization.name,
                    "prefix": organization.prefix,
                    "description": organization.description,
                },
                "membership": {
                    "points": user_points,
                    "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                    "points_history": points_history,
                },
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/users", methods=["POST"])
@auth_required
@error_handler
def add_user_to_organization(org_prefix):
    """Add a user to a specific organization"""
    data = request.json
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization
        from modules.points.api import link_or_create_user

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Validate required fields
        if not data.get("name") and not data.get("username"):
            return jsonify({"error": "Either name or username is required"}), 400

        # Use the link_or_create_user function from points API
        user_data = {
            "username": data.get("username"),
            "email": data.get("email"),
            "name": data.get("name"),
            "asu_id": data.get("asu_id") if data.get("asu_id") and data.get("asu_id") != "N/A" else None,
            "academic_standing": data.get("academic_standing", "N/A"),
            "major": data.get("major", "N/A"),
        }

        user = link_or_create_user(organization.id, user_data, data.get("discord_id"))

        if not user:
            return jsonify({"error": "Failed to create or link user"}), 500

        return jsonify(
            {
                "message": "User added to organization successfully",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    "discord_linked": bool(user.discord_id),
                },
                "organization": {"name": organization.name, "prefix": organization.prefix},
            }
        ), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
