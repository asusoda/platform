import csv
import threading
import time
import uuid
from io import StringIO

from flask import Blueprint, jsonify, request, session
from sqlalchemy import and_, case, func, or_

from modules.auth.decoraters import auth_required
from modules.points.models import Points, User
from modules.utils.logging_config import logger
from shared import db_connect, tokenManger

points_blueprint = Blueprint("points", __name__, template_folder=None, static_folder=None)

LEADERBOARD_CACHE_TTL = 300  # 5 minutes in seconds
leaderboard_cache = {}


def update_user_field(db, user, field_name, field_value, organization_id=None):
    """
    Helper function to update a specific user field with validation.

    Args:
        db: Database session
        user: User object to update
        field_name: Name of the field to update
        field_value: New value for the field
        organization_id: Optional organization ID for membership validation

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Validate field exists on User model
        if not hasattr(user, field_name):
            return False, f"Invalid field: {field_name}"

        # Special validation for unique fields
        if field_name in ["username", "email", "discord_id", "asu_id"] and field_value:
            existing = db.query(User).filter(getattr(User, field_name) == field_value).first()
            if existing and existing.id != user.id:
                return False, f"{field_name} is already taken"

        # Update the field
        setattr(user, field_name, field_value)
        db.commit()

        return True, f"{field_name} updated successfully"

    except Exception as e:
        db.rollback()
        return False, str(e)


def manage_user_in_organization(db, organization_id, user_data, discord_id=None, user_identifier=None):
    """
    Unified function to create, update, or link users in an organization.

    Args:
        db: Database session
        organization_id: ID of the organization
        user_data: Dictionary containing user information
        discord_id: Optional Discord ID to link
        user_identifier: Optional identifier to find existing user (email, uuid, username)

    Returns:
        tuple: (user: User|None, success: bool, message: str)
    """
    try:
        from modules.points.models import UserOrganizationMembership

        user = None

        # Try to find existing user
        if user_identifier:
            # Find by identifier
            user = db.query(User).filter_by(email=user_identifier).first()
            if not user:
                user = db.query(User).filter_by(uuid=user_identifier).first()
            if not user:
                user = db.query(User).filter_by(username=user_identifier).first()

        if not user and user_data.get("email"):
            # Try to find by email from user_data
            user = db.query(User).filter_by(email=user_data["email"]).first()

        if not user and user_data.get("asu_id") and user_data["asu_id"] != "N/A":
            # Try to find by ASU ID
            user = db.query(User).filter_by(asu_id=user_data["asu_id"]).first()

        if not user and discord_id:
            # Try to find by Discord ID
            user = db.query(User).filter_by(discord_id=discord_id).first()

        if user:
            # Update existing user
            updated_fields = []
            for field, value in user_data.items():
                if value is not None and hasattr(user, field):
                    current_value = getattr(user, field)
                    if current_value != value:
                        success, message = update_user_field(db, user, field, value, organization_id)
                        if success:
                            updated_fields.append(field)
                        else:
                            return user, False, message

            # Link Discord ID if provided and not already linked
            if discord_id and not user.discord_id:
                success, message = update_user_field(db, user, "discord_id", discord_id, organization_id)
                if success:
                    updated_fields.append("discord_id")

            # Ensure user is member of organization
            membership = (
                db.query(UserOrganizationMembership)
                .filter_by(user_id=user.id, organization_id=organization_id, is_active=True)
                .first()
            )

            if not membership:
                new_membership = UserOrganizationMembership(user_id=user.id, organization_id=organization_id)
                db.add(new_membership)
                db.commit()
                updated_fields.append("organization_membership")

            action = "updated" if updated_fields else "found"
            message = f"User {action}" + (f" ({', '.join(updated_fields)})" if updated_fields else "")
            return user, True, message

        else:
            # Create new user
            new_user = User(
                discord_id=discord_id,
                username=user_data.get("username"),  # Can be None
                name=user_data.get("name", "Unknown"),
                email=user_data.get("email"),
                asu_id=user_data.get("asu_id")
                if user_data.get("asu_id") and user_data.get("asu_id") != "N/A"
                else None,
                academic_standing=user_data.get("academic_standing", "N/A"),
                major=user_data.get("major", "N/A"),
                uuid=str(uuid.uuid4()),
            )

            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            # Add membership to organization
            membership = UserOrganizationMembership(user_id=new_user.id, organization_id=organization_id)
            db.add(membership)
            db.commit()

            return new_user, True, "User created successfully"

    except Exception as e:
        db.rollback()
        return None, False, str(e)


def get_or_create_user(discord_id, organization_id, username=None):
    """
    Get existing user or create new user and add them to the organization.
    This is called when a guild member accesses member endpoints.
    """
    db = next(db_connect.get_db())
    try:
        user_data = {"username": username, "name": username or f"User_{discord_id}"}

        user, success, message = manage_user_in_organization(db, organization_id, user_data, discord_id=discord_id)

        if success:
            print(f"✅ [DEBUG] {message} - User {user.id} in org {organization_id}")
            return user
        else:
            print(f"❌ [DEBUG] Error: {message}")
            return None

    except Exception as e:
        print(f"❌ [DEBUG] Error creating user: {e}")
        return None
    finally:
        db.close()


def link_or_create_user(organization_id, user_data, discord_id=None):
    """
    Link existing user account or create new user for member store access.
    Handles account linking based on ASU ID, email, or username.
    """
    db = next(db_connect.get_db())
    try:
        user, success, message = manage_user_in_organization(db, organization_id, user_data, discord_id=discord_id)

        if success:
            print(f"✅ [DEBUG] {message} - User {user.id if user else 'None'} for org {organization_id}")
            return user
        else:
            print(f"❌ [DEBUG] Error: {message}")
            return None

    except Exception as e:
        print(f"❌ [DEBUG] Error linking/creating user: {e}")
        return None
    finally:
        db.close()


def process_csv_in_background(file_content, event_name, event_points, org_prefix):
    """Process CSV in background for a specific organization"""
    csv_file = StringIO(file_content)
    csv_reader = csv.DictReader(csv_file)

    db = next(db_connect.get_db())
    success_count = 0
    errors = []
    processed_emails = set()

    try:
        from modules.organizations.models import Organization

        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            errors.append(f"Organization {org_prefix} not found")
            return

        for row in csv_reader:
            if not row.get("Checked-In Date"):
                continue

            email = row.get("Email")
            first_name = row.get("First Name", "")
            last_name = row.get("Last Name", "")
            name = f"{first_name} {last_name}".strip()

            if not email or not name:
                errors.append(f"Missing required fields (Email, Name) in row: {row}")
                continue

            if email in processed_emails:
                continue  # Skip to the next row to prevent duplicate points.

            user = db.query(User).filter_by(email=email).first()

            if not user:
                user_data = {"email": email, "name": name, "asu_id": None, "academic_standing": "N/A", "major": "N/A"}
                user, success, message = manage_user_in_organization(db, organization.id, user_data)
                if not success:
                    errors.append(f"Failed to create user {email}: {message}")
                    continue

            point = Points(
                points=event_points,
                event=event_name,
                awarded_by_officer="CSV Upload",
                user_id=user.id,
                organization_id=organization.id,
            )
            db.add(point)
            db.commit()

            processed_emails.add(email)
            success_count += 1

    except Exception as e:
        errors.append(f"An unexpected error occurred: {str(e)}")
    finally:
        db.close()

    print(
        f"CSV processing finished for org '{org_prefix}'. Awarded points to {success_count} users. Errors: {len(errors)}"
    )
    if errors:
        print("Errors encountered:", errors)


# API Routes
@points_blueprint.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Points"}), 200


@points_blueprint.route("/<string:org_prefix>/member_login", methods=["POST"])
def member_login(org_prefix):
    """
    Member login endpoint for public store access.
    Links or creates user account based on provided information.
    """
    data = request.json

    # Validate required fields
    if not data:
        return jsonify({"error": "Request data is required"}), 400

    # Get organization
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization

        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Extract user data
        user_data = {
            "name": data.get("name"),
            "username": data.get("username"),
            "email": data.get("email"),
            "asu_id": data.get("asu_id"),
            "academic_standing": data.get("academic_standing"),
            "major": data.get("major"),
        }

        # Get discord_id from session if available
        discord_id = session.get("discord_id")

        # Link or create user
        user = link_or_create_user(organization.id, user_data, discord_id)

        if not user:
            return jsonify({"error": "Failed to create or link user account"}), 500

        # Store user info in session for member access
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
                    "asu_id": user.asu_id,
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
    """
    Get member profile with organization memberships and points.
    """
    # Get member user from session
    member_user_id = session.get("member_user_id")
    session.get("member_org_id")

    if not member_user_id:
        return jsonify({"error": "Member not logged in"}), 401

    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Get user
        user = db.query(User).filter_by(id=member_user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Get user's organization memberships
        memberships = db.query(UserOrganizationMembership).filter_by(user_id=user.id, is_active=True).all()

        # Get organizations user is a member of
        org_data = []
        total_points_all_orgs = 0
        current_org_points = 0

        for membership in memberships:
            org = db.query(Organization).filter_by(id=membership.organization_id).first()
            if org:
                # Get points for this organization
                org_points = (
                    db.query(func.sum(Points.points)).filter_by(user_id=user.id, organization_id=org.id).scalar() or 0
                )

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
                    "asu_id": user.asu_id,
                    "academic_standing": user.academic_standing,
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
    """Unified endpoint to create, update, or link users in an organization"""
    data = request.json
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Extract user data and identifiers
        user_data = {
            "username": data.get("username"),
            "email": data.get("email"),
            "name": data.get("name"),
            "asu_id": data.get("asu_id"),
            "academic_standing": data.get("academic_standing"),
            "major": data.get("major"),
        }

        # Remove None values to avoid overwriting existing data with None
        user_data = {k: v for k, v in user_data.items() if v is not None}

        discord_id = data.get("discord_id")
        user_identifier = data.get("user_identifier")  # email, uuid, or username to find existing user

        user, success, message = manage_user_in_organization(
            db, organization.id, user_data, discord_id, user_identifier
        )

        if not success:
            return jsonify({"error": message}), 400

        return jsonify(
            {
                "message": message,
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
    """Add points to a user in a specific organization"""
    data = request.json
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 400

        # Check if the user exists by discord_id
        user = db.query(User).filter_by(discord_id=data["user_discord_id"]).first()
        if not user:
            return jsonify({"error": "User does not exist"}), 404

        # Add points to the user
        point = Points(
            points=data["points"],
            user_id=user.id,
            organization_id=organization.id,
            event=data.get("event"),
            awarded_by_officer=data.get("awarded_by_officer"),
        )
        db.add(point)
        db.commit()
        db.refresh(point)

        return jsonify(
            {
                "id": point.id,
                "points": point.points,
                "user_id": point.user_id,
                "organization_id": point.organization_id,
                "event": point.event,
                "awarded_by_officer": point.awarded_by_officer,
                "timestamp": point.timestamp.isoformat() if point.timestamp else None,
                "last_updated": point.last_updated.isoformat() if point.last_updated else None,
            }
        ), 201

    except Exception as e:
        db.rollback()
        logger.error(f"Error in addPointsToUserByAsuId: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while adding points"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/users", methods=["GET"])
@auth_required
def get_org_users(org_prefix):
    """Get all users for a specific organization with comprehensive information"""
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
                        "uuid": user.uuid,
                        "name": user.name,
                        "username": user.username,
                        "email": user.email,
                        "asu_id": user.asu_id,
                        "academic_standing": user.academic_standing,
                        "major": user.major,
                        "discord_linked": bool(user.discord_id),
                        "points": user_points,
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
    """Get all points for a specific organization"""
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Filter points by organization
        points = db.query(Points).filter_by(organization_id=organization.id).all()

        return jsonify(
            [
                {
                    "id": point.id,
                    "points": point.points,
                    "event": point.event,
                    "awarded_by_officer": point.awarded_by_officer,
                    "timestamp": point.timestamp.isoformat() if point.timestamp else None,
                    "last_updated": point.last_updated.isoformat() if point.last_updated else None,
                    "user_id": point.user_id,
                    "organization_id": point.organization_id,
                }
                for point in points
            ]
        ), 200

    except Exception as e:
        logger.error(f"Error in getAllPointsRecords: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving points records"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/leaderboard", methods=["GET"])
def get_org_leaderboard(org_prefix):
    """Get leaderboard for a specific organization"""
    token = None
    show_email = False  # Default to showing UUID unless authentication succeeds

    # Extract token from Authorization header
    if "Authorization" in request.headers:
        token = request.headers["Authorization"].split(" ")[1]  # Get the token part

    # If the token is present, validate it
    if token:
        try:
            # Check if the token is valid and not expired
            if tokenManger.is_token_valid(token) and not tokenManger.is_token_expired(token):
                show_email = True  # If valid, set to show email
            elif tokenManger.is_token_expired(token):
                return jsonify({"message": "Token is expired!"}), 403  # Expired token
        except Exception as e:
            return jsonify({"message": str(e)}), 401  # Token is invalid or some error occurred

    cache_key = (org_prefix, show_email)
    cache_entry = leaderboard_cache.get(cache_key)
    current_time = time.time()
    if cache_entry and current_time - cache_entry["timestamp"] < LEADERBOARD_CACHE_TTL:
        return jsonify(cache_entry["data"]), 200

    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        leaderboard_rows = (
            db.query(
                User.id.label("user_id"),
                User.name,
                User.email,
                User.uuid,
                func.coalesce(func.sum(case((Points.points > 0, Points.points), else_=0)), 0).label("total_points"),
            )
            .select_from(User)
            .outerjoin(
                Points,
                and_(
                    Points.user_id == User.id,
                    Points.organization_id == organization.id,
                ),
            )
            .outerjoin(
                UserOrganizationMembership,
                and_(
                    UserOrganizationMembership.user_id == User.id,
                    UserOrganizationMembership.organization_id == organization.id,
                    UserOrganizationMembership.is_active,
                ),
            )
            .filter(or_(Points.id.isnot(None), UserOrganizationMembership.id.isnot(None)))
            .group_by(User.id, User.name, User.email, User.uuid)
            .order_by(
                func.coalesce(func.sum(case((Points.points > 0, Points.points), else_=0)), 0).desc(),
                User.name.asc(),
            )
            .all()
        )

        user_ids = [row.user_id for row in leaderboard_rows]
        points_details_map = {user_id: [] for user_id in user_ids}

        if user_ids:
            details = (
                db.query(
                    Points.user_id,
                    Points.event,
                    Points.points,
                    Points.timestamp,
                )
                .filter(
                    Points.organization_id == organization.id,
                    Points.user_id.in_(user_ids),
                )
                .order_by(Points.user_id, Points.timestamp.desc())
                .all()
            )

            for user_id, event, points, timestamp in details:
                points_details_map.setdefault(user_id, []).append(
                    {
                        "event": event,
                        "points": float(points) if points is not None else 0,
                        "timestamp": timestamp.isoformat() if timestamp else None,
                    }
                )

        response_payload = [
            {
                "name": row.name,
                "identifier": row.email if (show_email and row.email) else row.uuid,
                "total_points": float(row.total_points) if row.total_points is not None else 0,
                "points_details": points_details_map.get(row.user_id, []),
            }
            for row in leaderboard_rows
        ]

        leaderboard_cache[cache_key] = {
            "timestamp": time.time(),
            "data": response_payload,
        }

        return jsonify(response_payload), 200

    except Exception as e:
        logger.error(f"Error in getLeaderboard: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving leaderboard"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/uploadEventCSV", methods=["POST"])
@auth_required
def upload_event_csv(org_prefix):
    """Upload event CSV for a specific organization"""
    if "file" not in request.files or "event_name" not in request.form or "event_points" not in request.form:
        return jsonify({"error": "Missing required fields"}), 400

    file = request.files["file"]
    event_name = request.form["event_name"]
    event_points = int(request.form["event_points"])

    # Check file extension
    if not file.filename.endswith(".csv"):
        return jsonify({"error": "File must be a CSV"}), 400

    # Read the file content
    file_content = file.stream.read().decode("utf-8")

    # Start a new thread to process the CSV in the background
    background_thread = threading.Thread(
        target=process_csv_in_background, args=(file_content, event_name, event_points, org_prefix)
    )
    background_thread.start()

    # Return an immediate response while the CSV is being processed
    return jsonify({"message": "File is being processed in the background."}), 202


@points_blueprint.route("/<string:org_prefix>/getUserPoints", methods=["GET"])
@auth_required
def get_user_points_in_org(org_prefix):
    """Get user points in a specific organization"""
    discord_id = request.args.get("discord_id")

    if not discord_id:
        return jsonify({"error": "discord_id parameter is missing"}), 400

    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Check if the user exists
        user = db.query(User).filter_by(discord_id=discord_id).first()
        if not user:
            return jsonify({"error": "User does not exist"}), 404  # Not Found status code

        # Query all points earned by the user in the specific organization
        points_records = db.query(Points).filter_by(user_id=user.id, organization_id=organization.id).all()

        if not points_records:
            return jsonify({"message": "No points earned by this user in this organization"}), 200

        return jsonify(
            [
                {
                    "id": record.id,
                    "points": record.points,
                    "event": record.event,
                    "awarded_by_officer": record.awarded_by_officer,
                    "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                    "organization_id": record.organization_id,
                    "last_updated": record.last_updated.isoformat() if record.last_updated else None,
                }
                for record in points_records
            ]
        ), 200

    except Exception as e:
        logger.error(f"Error in getPointsHistoryByDiscordId: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving points history"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/getUserTotalPoints", methods=["GET"])
@auth_required
def get_user_total_points_in_org(org_prefix):
    """Get user total points in a specific organization"""
    discord_id = request.args.get("discord_id")

    if not discord_id:
        return jsonify({"error": "discord_id parameter is missing"}), 400

    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Check if the user exists
        user = db.query(User).filter_by(discord_id=discord_id).first()
        if not user:
            return jsonify({"error": "User does not exist"}), 404

        # Calculate total points for the user in the specific organization
        total_points = (
            db.query(func.sum(Points.points)).filter_by(user_id=user.id, organization_id=organization.id).scalar()
            or 0.0
        )

        return jsonify(
            {
                "user_id": user.id,
                "discord_id": user.discord_id,
                "username": user.username,
                "organization_id": organization.id,
                "total_points": total_points,
            }
        ), 200

    except Exception as e:
        logger.error(f"Error in getUserPointsByDiscordId: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving user points"}), 400
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/assignPoints", methods=["POST"])
@points_blueprint.route("/<string:org_prefix>/assign_points", methods=["POST"])  # Add alias for frontend compatibility
@auth_required
def assign_points_to_org(org_prefix):
    """Assign points to a user in a specific organization"""
    data = request.json
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Validate required fields
        if not data.get("user_identifier"):
            return jsonify({"error": "user_identifier is required"}), 400
        if not data.get("points"):
            return jsonify({"error": "points is required"}), 400

        user_identifier = data["user_identifier"]

        # Try to find user by email first, then UUID, then username
        user = db.query(User).filter_by(email=user_identifier).first()
        if not user:
            user = db.query(User).filter_by(uuid=user_identifier).first()
        if not user:
            user = db.query(User).filter_by(username=user_identifier).first()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Check if user is a member of this organization
        membership = (
            db.query(UserOrganizationMembership)
            .filter_by(user_id=user.id, organization_id=organization.id, is_active=True)
            .first()
        )

        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 400

        # Add points to the user
        point = Points(
            points=float(data["points"]),
            user_id=user.id,
            organization_id=organization.id,
            event=data.get("event"),
            awarded_by_officer=data.get("awarded_by_officer"),
        )
        db.add(point)
        db.commit()
        db.refresh(point)

        return jsonify(
            {
                "message": "Points assigned successfully",
                "points": {
                    "id": point.id,
                    "points": point.points,
                    "user_id": point.user_id,
                    "organization_id": point.organization_id,
                    "event": point.event,
                    "awarded_by_officer": point.awarded_by_officer,
                    "timestamp": point.timestamp.isoformat() if point.timestamp else None,
                    "last_updated": point.last_updated.isoformat() if point.last_updated else None,
                },
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
    """Delete points by event for a specific organization"""
    data = request.json
    if not data or "user_email" not in data or "event" not in data:
        return jsonify({"error": "user_email and event are required"}), 400

    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Find user by email first
        user = db.query(User).filter_by(email=data["user_email"]).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Find the points entry by user_id and event name in this organization
        points_entry = (
            db.query(Points).filter_by(user_id=user.id, organization_id=organization.id, event=data["event"]).first()
        )

        if not points_entry:
            return jsonify({"error": "Points entry not found"}), 404

        # Delete the points entry
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
    """Update specific user fields in an organization"""
    data = request.json
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Find user by email, UUID, or username
        user = db.query(User).filter_by(email=user_identifier).first()
        if not user:
            user = db.query(User).filter_by(uuid=user_identifier).first()
        if not user:
            user = db.query(User).filter_by(username=user_identifier).first()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Check if user is a member of this organization
        membership = (
            db.query(UserOrganizationMembership)
            .filter_by(user_id=user.id, organization_id=organization.id, is_active=True)
            .first()
        )

        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 400

        # Update fields using the helper function
        updated_fields = []
        errors = []

        for field_name, field_value in data.items():
            if field_name == "user_identifier":  # Skip meta fields
                continue

            success, message = update_user_field(db, user, field_name, field_value, organization.id)
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
                    "asu_id": user.asu_id,
                    "academic_standing": user.academic_standing,
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
    """Get user's points in a specific organization"""
    db = next(db_connect.get_db())
    try:
        from modules.organizations.models import Organization
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        organization = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        # Find user
        user = db.query(User).filter_by(email=user_identifier).first()
        if not user:
            user = db.query(User).filter_by(uuid=user_identifier).first()
        if not user:
            user = db.query(User).filter_by(username=user_identifier).first()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Check if user is a member of this organization
        membership = (
            db.query(UserOrganizationMembership)
            .filter_by(user_id=user.id, organization_id=organization.id, is_active=True)
            .first()
        )

        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 400

        # Get user's points in this organization
        total_points = (
            db.query(func.sum(Points.points)).filter_by(user_id=user.id, organization_id=organization.id).scalar() or 0
        )

        # Get points history
        points_records = (
            db.query(Points)
            .filter_by(user_id=user.id, organization_id=organization.id)
            .order_by(Points.last_updated.desc())
            .all()
        )

        return jsonify(
            {
                "user": {"id": user.id, "name": user.name, "email": user.email, "username": user.username},
                "organization": {"name": organization.name, "prefix": organization.prefix},
                "total_points": total_points,
                "points_history": [
                    {
                        "id": record.id,
                        "points": record.points,
                        "event": record.event,
                        "awarded_by_officer": record.awarded_by_officer,
                        "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                        "last_updated": record.last_updated.isoformat() if record.last_updated else None,
                    }
                    for record in points_records
                ],
            }
        ), 200

    except Exception as e:
        logger.error(f"Error in getUserPointsByAsuId: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while retrieving user points"}), 500
    finally:
        db.close()
