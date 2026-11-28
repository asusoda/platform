import os

from flask import Blueprint, jsonify, send_from_directory
from sqlalchemy import func

from core.db import db_connect
from core.http.responses import error_handler, internal_error
from modules.auth.access import member_details_allowed
from modules.members.models import User, UserOrganizationMembership
from modules.organizations.service import find_by_prefix
from modules.points.models import Points
from modules.points.submodules.leaderboard import service as leaderboards
from modules.points.submodules.store.models import Order, Product

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


@public_blueprint.route("/<string:org_prefix>/leaderboard", methods=["GET"])
@error_handler
def get_leaderboard(org_prefix):
    """Get leaderboard for a specific organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        leaderboard_data = leaderboards.public_leaderboard(db, org, member_details_allowed(org))

    except Exception:
        return internal_error("get_leaderboard")
    finally:
        db.close()

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
    db = next(db_connect.get_db())
    try:
        leaderboard = leaderboards.global_leaderboard(db)
    except Exception:
        return internal_error("get_global_leaderboard")
    finally:
        db.close()

    return jsonify(leaderboard), 200


@public_blueprint.route("/<string:org_prefix>/users", methods=["GET"])
@error_handler
def get_organization_users(org_prefix):
    """Get all users for a specific organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        users_query = (
            db.query(User)
            .join(UserOrganizationMembership, User.id == UserOrganizationMembership.user_id)
            .filter(UserOrganizationMembership.organization_id == org.id)
            .filter(UserOrganizationMembership.is_active)
            .all()
        )

        show_details = member_details_allowed(org)
        users = []
        for user in users_query:
            entry = {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "discord_linked": bool(user.discord_id),
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            if show_details:
                entry.update({"email": user.email, "asu_id": user.student_id})
            users.append(entry)

        return jsonify(
            {
                "organization": {"name": org.name, "prefix": org.prefix, "description": org.description},
                "users": users,
            }
        ), 200

    except Exception:
        return internal_error("get_organization_users")
    finally:
        db.close()


@public_blueprint.route("/<string:org_prefix>/stats", methods=["GET"])
@error_handler
def get_organization_stats(org_prefix):
    """Get statistics for a specific organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        user_count = (
            db.query(UserOrganizationMembership)
            .filter(UserOrganizationMembership.organization_id == org.id, UserOrganizationMembership.is_active)
            .count()
        )

        total_points = db.query(func.sum(Points.points)).filter(Points.organization_id == org.id).scalar() or 0

        product_count = db.query(Product).filter(Product.organization_id == org.id).count()

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

    except Exception:
        return internal_error("get_organization_stats")
    finally:
        db.close()
