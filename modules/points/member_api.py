"""Member and public routes of points: the store sign-in, the member profile and the leaderboard.

The routes register on points_blueprint. modules/registry.py imports the blueprint from here, so they
register before the blueprint is mounted.
"""

from flask import jsonify, request, session

from core.db import db_connect
from core.http.cached import cached_json, org_key
from core.http.request_log import bearer_token
from core.log import get_logger
from modules.auth.access import decide, discord_directory
from modules.auth.tokens import token_manager
from modules.points import service
from modules.points.api import ORG_NOT_FOUND, active_org, points_blueprint
from modules.points.submodules.leaderboard import service as leaderboards

__all__ = ["points_blueprint"]

logger = get_logger(__name__)

LEADERBOARD_CACHE_TTL = 300  # seconds


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
        logger.debug("member_login clerk token check failed", exc_info=True)
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

    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404
        body = service.member_login(db, organization, data, session.get("discord_id"))
        session["member_user_id"] = body["user"]["id"]
        session["member_org_id"] = organization.id
        return jsonify(body), 200
    except service.PointsError as e:
        return jsonify({"error": e.message}), e.status
    except Exception:
        db.rollback()
        logger.exception("member_login failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while retrieving user points"}), 500
    finally:
        db.close()


@points_blueprint.route("/<string:org_prefix>/member_profile", methods=["GET"])
def get_member_profile(org_prefix):
    """The signed-in member's profile, orgs and points. A Discord session (the store sign-in) comes first."""
    discord_id = session.get("discord_id")
    member_user_id = session.get("member_user_id")
    if not discord_id and not member_user_id:
        return jsonify({"error": "Member not logged in"}), 401

    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404
        # As member_required: a Discord user must be in the org's server
        directory = discord_directory() if discord_id else None
        return jsonify(service.member_profile(db, organization, discord_id, member_user_id, directory)), 200
    except service.PointsError as e:
        return jsonify({"error": e.message}), e.status
    except Exception:
        logger.exception("member_profile failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while retrieving user points across organizations"}), 500
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
    except Exception:
        return None, (jsonify({"message": "Token is invalid!"}), 401)
    return False, None


@points_blueprint.route("/<string:org_prefix>/leaderboard", methods=["GET"])
def get_org_leaderboard(org_prefix):
    """The org's leaderboard. A valid platform token shows emails; without one it shows uuids."""
    show_email, refusal = _leaderboard_show_email()
    if refusal is not None:
        return refusal

    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 404
        return cached_json(
            org_key(org_prefix, "points", "leaderboard", bool(show_email)),
            LEADERBOARD_CACHE_TTL,
            lambda: leaderboards.officer_leaderboard(db, organization, bool(show_email)),
        )
    except Exception:
        logger.exception("leaderboard failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while retrieving leaderboard"}), 400
    finally:
        db.close()
