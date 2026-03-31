import os
from datetime import datetime

from flask import Blueprint, jsonify, send_from_directory
from sqlalchemy import and_, case, func

from modules.auth.decoraters import error_handler
from modules.points.models import Points, User
from modules.utils.db import db_connect

# Update the blueprint to include the static folder
public_blueprint = Blueprint(
    "public",
    __name__,
    template_folder=None,
    static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
    static_url_path="/static/public",
)


@public_blueprint.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(public_blueprint.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon"
    )


@public_blueprint.route("/getnextevent", methods=["GET"])
def get_next_event():
    pass


# Helper function to get organization by prefix
def get_organization_by_prefix(db, org_prefix):
    from modules.organizations.models import Organization

    org = db.query(Organization).filter(Organization.prefix == org_prefix).first()
    if not org:
        return None
    return org


@public_blueprint.route("/<string:org_prefix>/leaderboard", methods=["GET"])
@error_handler
def get_leaderboard(org_prefix):
    """Get leaderboard for a specific organization"""
    db = next(db_connect.get_db())
    try:
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        # Get all users who are members of this organization with their points
        leaderboard_query = (
            db.query(
                User.name, User.email, User.asu_id, func.coalesce(func.sum(Points.points), 0).label("total_points")
            )
            .join(UserOrganizationMembership, User.id == UserOrganizationMembership.user_id)
            .outerjoin(Points, and_(Points.user_id == User.id, Points.organization_id == org.id))
            .filter(UserOrganizationMembership.organization_id == org.id)
            .filter(UserOrganizationMembership.is_active)
            .group_by(User.id, User.name, User.email, User.asu_id)
            .order_by(func.sum(Points.points).desc(), User.name.asc())
            .all()
        )

        # Format leaderboard data
        leaderboard_data = []
        for name, email, asu_id, total_points in leaderboard_query:
            leaderboard_data.append(
                {
                    "name": name,
                    "email": email,
                    "asu_id": asu_id,
                    "total_points": float(total_points) if total_points else 0.0,
                }
            )

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

    # Return the leaderboard data
    return jsonify(
        {
            "organization": {"name": org.name, "prefix": org.prefix, "description": org.description},
            "leaderboard": leaderboard_data,
        }
    ), 200


@public_blueprint.route("/leaderboard", methods=["GET"])
@error_handler
def get_global_leaderboard():
    """Get global leaderboard (legacy endpoint - all organizations combined)"""
    start_date = datetime(2025, 1, 1)  # Jan 1, 2025
    end_date = datetime(2025, 5, 12)  # May 12, 2025
    db = next(db_connect.get_db())
    try:
        # First, get the total points and names of all users
        leaderboard = (
            db.query(
                User.name,
                func.coalesce(func.sum(Points.points), 0).label("total_points"),
                User.uuid,
                func.coalesce(
                    func.sum(
                        case(
                            (and_(Points.timestamp >= start_date, Points.timestamp <= end_date), Points.points), else_=0
                        )
                    ),
                    0,
                ).label("curr_sem_points"),
            )
            .outerjoin(Points)  # Ensure users with no points are included
            .group_by(User.uuid)
            .order_by(func.sum(Points.points).desc(), User.name.asc())  # Sort by points then by name
            .all()
        )

        # Then, get the detailed points information for each user
        user_details = {}
        for user in db.query(User).all():
            points_details = (
                db.query(Points.event, Points.points, Points.timestamp, Points.awarded_by_officer)
                .filter(Points.user_id == user.id)
                .all()
            )
            # Format points details as a list of dictionaries
            user_details[user.uuid] = [
                {
                    "event": detail.event,
                    "points": detail.points,
                    "timestamp": detail.timestamp.isoformat() if detail.timestamp else None,
                    "awarded_by": detail.awarded_by_officer,
                }
                for detail in points_details
            ]

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

    # Combine the leaderboard and detailed points information
    return jsonify(
        [
            {
                "name": name,
                "total_points": total_points,
                "points_details": user_details.get(uuid, []),  # Get details or empty list if none
                "curr_sem_points": curr_sem_points,
            }
            for name, total_points, uuid, curr_sem_points in leaderboard
        ]
    ), 200


@public_blueprint.route("/<string:org_prefix>/users", methods=["GET"])
@error_handler
def get_organization_users(org_prefix):
    """Get all users for a specific organization"""
    db = next(db_connect.get_db())
    try:
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        # Get all users who are members of this organization
        users_query = (
            db.query(User)
            .join(UserOrganizationMembership, User.id == UserOrganizationMembership.user_id)
            .filter(UserOrganizationMembership.organization_id == org.id)
            .filter(UserOrganizationMembership.is_active)
            .all()
        )

        return jsonify(
            {
                "organization": {"name": org.name, "prefix": org.prefix, "description": org.description},
                "users": [
                    {
                        "id": user.id,
                        "name": user.name,
                        "email": user.email,
                        "asu_id": user.asu_id,
                        "username": user.username,
                        "discord_linked": bool(user.discord_id),
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                    }
                    for user in users_query
                ],
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@public_blueprint.route("/<string:org_prefix>/stats", methods=["GET"])
@error_handler
def get_organization_stats(org_prefix):
    """Get statistics for a specific organization"""
    db = next(db_connect.get_db())
    try:
        from modules.points.models import UserOrganizationMembership

        # Get organization by prefix
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        # Get user count (members of this organization)
        user_count = (
            db.query(UserOrganizationMembership)
            .filter(UserOrganizationMembership.organization_id == org.id, UserOrganizationMembership.is_active)
            .count()
        )

        # Get total points awarded in this organization
        total_points = db.query(func.sum(Points.points)).filter(Points.organization_id == org.id).scalar() or 0

        # Get product count
        from modules.storefront.models import Product

        product_count = db.query(Product).filter(Product.organization_id == org.id).count()

        # Get order count
        from modules.storefront.models import Order

        order_count = db.query(Order).filter(Order.organization_id == org.id).count()

        return jsonify(
            {
                "organization": {"name": org.name, "prefix": org.prefix, "description": org.description},
                "stats": {
                    "user_count": user_count,
                    "total_points_awarded": float(total_points),
                    "product_count": product_count,
                    "order_count": order_count,
                },
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
