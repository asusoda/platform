import functools
import logging
from functools import wraps

from flask import jsonify, request, session

from modules.auth.access import (
    discord_directory,
    is_superadmin,
    officer_guild_ids,
    org_officer_denial,
    superadmin_denial,
)
from shared import tokenManager

logger = logging.getLogger(__name__)


def dual_auth_required(f):
    """
    A decorator that accepts both Clerk tokens and Discord OAuth tokens.
    Tries Clerk authentication first, then falls back to Discord OAuth.
    Sets request.clerk_user_email on successful authentication (Clerk or Discord OAuth).
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None

        # Extract token from Authorization header
        if auth_header.startswith("Bearer "):
            parts = auth_header.split(" ", 1)
            if len(parts) >= 2 and parts[1].strip():
                token = parts[1].strip()

        # Try Clerk authentication first if we have a Bearer token
        if token:
            try:
                from core.clerk_auth import verify_clerk_token

                result = verify_clerk_token(token)
                if result:
                    email, clerk_user = result
                    # Clerk authentication successful
                    logger.debug(f"Dual auth: Clerk authentication successful for {email}")
                    request.clerk_user_email = email  # type: ignore[attr-defined]
                    request.clerk_user = clerk_user  # type: ignore[attr-defined]
                    return f(*args, **kwargs)
                else:
                    logger.debug("Dual auth: Clerk token verification failed, trying Discord OAuth")
            except Exception as e:
                logger.debug(f"Dual auth: Clerk verification error: {e}, trying Discord OAuth")

        # Fall back to Discord OAuth authentication
        # Check session cookie first
        if session.get("token"):
            try:
                if not tokenManager.is_token_valid(session["token"]):
                    session.pop("token", None)
                    return jsonify({"message": "Session token is invalid!"}), 401
                elif tokenManager.is_token_expired(session["token"]):
                    session.pop("token", None)
                    return jsonify({"message": "Session token has expired!"}), 401

                # Discord OAuth session authentication successful
                logger.debug("Dual auth: Discord OAuth session authentication successful")
                # Set clerk_user_email from session if available for compatibility
                username = tokenManager.retrieve_username(session["token"])
                if username:
                    request.clerk_user_email = username  # type: ignore[attr-defined]
                return f(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Dual auth: Session authentication error: {e}")
                session.pop("token", None)

        # Check Authorization header for Discord OAuth token
        if not token:
            return jsonify({"message": "Authentication required!"}), 401

        try:
            if not tokenManager.is_token_valid(token):
                logger.debug("Dual auth: Discord OAuth token is invalid")
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManager.is_token_expired(token):
                logger.debug("Dual auth: Discord OAuth token is expired")
                return jsonify({"message": "Token is expired!"}), 403

            # Discord OAuth token authentication successful
            logger.debug("Dual auth: Discord OAuth token authentication successful")
            # Set clerk_user_email from token for compatibility
            username = tokenManager.retrieve_username(token)
            if username:
                request.clerk_user_email = username  # type: ignore[attr-defined]
            return f(*args, **kwargs)
        except Exception as e:
            logger.debug(f"Dual auth: Discord OAuth token authentication error: {e}")
            return jsonify({"message": "Authentication failed due to an internal error."}), 401

    return wrapper


def auth_required(f):
    """
    A decorator for Flask endpoints to ensure the user is authenticated.
    Checks both session cookies and Authorization headers.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        # Check session cookie first
        if session.get("token"):
            try:
                if not tokenManager.is_token_valid(session["token"]):
                    session.pop("token", None)
                    return jsonify({"message": "Session token is invalid!"}), 401
                elif tokenManager.is_token_expired(session["token"]):
                    session.pop("token", None)
                    return jsonify({"message": "Session token has expired!"}), 401
            except Exception:
                session.pop("token", None)
                return jsonify({"message": "Session authentication failed!"}), 401
            return _with_org_scope(f, *args, **kwargs)

        # If no session, check Authorization header (for API calls)
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return jsonify({"message": "Authentication required!"}), 401

        try:
            if not tokenManager.is_token_valid(token):
                logger.debug("Token is invalid")
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManager.is_token_expired(token):
                logger.debug("Token is expired")
                return jsonify({"message": "Token is expired!"}), 403
        except Exception as e:
            return jsonify({"message": str(e)}), 401
        return _with_org_scope(f, *args, **kwargs)

    return wrapper


def org_officer_required(f):
    """For routes behind dual_auth_required that only officers use: refuse members and other orgs' officers."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        return _with_org_scope(f, *args, **kwargs)

    return wrapper


def _with_org_scope(f, *args, **kwargs):
    """Run an authenticated route, refusing callers who are not officers of the org in its URL."""
    denial = org_officer_denial()
    if denial:
        message, status = denial
        return jsonify({"message": message}), status
    return f(*args, **kwargs)


def superadmin_required(f):
    """
    A decorator for API endpoints to ensure the user is a superadmin.
    Checks authentication and superadmin role.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        logger.debug(f"superadmin_required called for function: {f.__name__}")
        logger.debug(f"Request method: {request.method}")

        # First check authentication
        token = None

        # Check session cookie first
        logger.debug("Checking session token...")
        if session.get("token"):
            token = session.get("token")
            logger.debug("Found session token")
            try:
                logger.debug("Validating session token...")
                if not tokenManager.is_token_valid(token):
                    logger.debug("Session token is invalid!")
                    return jsonify({"message": "Token is invalid!"}), 401
                elif tokenManager.is_token_expired(token):
                    logger.debug("Session token is expired!")
                    return jsonify({"message": "Token is expired!"}), 403

                logger.debug("Session token is valid, checking role...")
                user_role = session.get("user", {}).get("role")
                logger.debug(f"User role from session: {user_role}")

                # Check superadmin role from session
                if user_role != "admin":
                    logger.debug(f"User role '{user_role}' is not admin!")
                    return jsonify({"message": "Superadmin access required!"}), 403

                logger.debug("Session authentication successful!")
                return f(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Error validating session token: {e}")
                return jsonify({"message": str(e)}), 401

        # Check Authorization header (for API calls)
        logger.debug("No session token, checking Authorization header...")
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            logger.debug("Authorization header present")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                logger.debug("Extracted Bearer token")
            else:
                logger.debug("Authorization header doesn't start with 'Bearer '")
                return jsonify({"message": "Invalid Authorization header format!"}), 401

        if not token:
            logger.debug("No token found in session or Authorization header!")
            return jsonify({"message": "Authentication required!"}), 401

        try:
            logger.debug("Validating API token...")
            if not tokenManager.is_token_valid(token):
                logger.debug("API token is invalid!")
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManager.is_token_expired(token):
                logger.debug("API token is expired!")
                return jsonify({"message": "Token is expired!"}), 403

            logger.debug("API token is valid, decoding...")
            # For API calls, we need to verify superadmin status from the token
            token_data = tokenManager.decode_token(token)
            if not token_data:
                logger.debug("Failed to decode token data!")
                return jsonify({"message": "Invalid token data!"}), 401

            logger.debug("Token decoded successfully")

            # Every token issued at login carries discord_id; tokens without it are refused
            discord_id = token_data.get("discord_id")
            if not discord_id:
                logger.debug("Token missing discord_id")
                return jsonify({"message": "Token missing user identification!"}), 401

            officer_guilds = officer_guild_ids(str(discord_id))
            if officer_guilds is None:
                return jsonify({"message": "Bot not available for verification!"}), 503
            if not officer_guilds and not is_superadmin(str(discord_id)):
                logger.debug("User is not an officer in any organization!")
                return jsonify({"message": "Superadmin access required!"}), 403

            denial = superadmin_denial(str(discord_id))
            if denial:
                return jsonify({"message": denial[0]}), denial[1]

            logger.debug("Superadmin authentication successful!")
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"General error in superadmin_required: {e}")
            import traceback

            traceback.print_exc()
            return jsonify({"message": str(e)}), 401

    return wrapper


def member_required(f):
    """
    Decorator that requires the user to be a member of the organization specified by org_prefix.
    Similar to auth_required but checks for guild membership instead of officer role.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            logger.debug(f"member_required decorator called for function: {f.__name__}")

            # Get the org_prefix from the URL parameters
            org_prefix = kwargs.get("org_prefix") or (args[0] if args else None)
            if not org_prefix:
                logger.debug("No org_prefix found in request")
                return jsonify({"message": "Organization prefix is required"}), 400

            logger.debug(f"Organization prefix: {org_prefix}")

            # Get Discord ID from session (same as auth_required)
            user_discord_id = session.get("discord_id")
            if not user_discord_id:
                logger.debug("No discord_id in session")
                return jsonify({"message": "Discord authentication required"}), 401

            logger.debug("User discord_id found in session")

            # Get organization from database
            try:
                from modules.organizations.models import Organization
                from shared import db_connect

                logger.debug("Getting database connection...")
                db = next(db_connect.get_db())

                logger.debug(f"Looking up organization with prefix: {org_prefix}")
                organization = (
                    db.query(Organization).filter(Organization.prefix == org_prefix, Organization.is_active).first()
                )

                if not organization:
                    logger.debug(f"Organization not found for prefix: {org_prefix}")
                    db.close()
                    return jsonify({"message": "Organization not found"}), 404

                logger.debug(f"Found organization: {organization.name}")
                db.close()

            except Exception as e:
                logger.error(f"Database error: {e}")
                if "db" in locals():
                    db.close()
                return jsonify({"message": f"Database error: {str(e)}"}), 500

            # Check if user is a member using the bot (same pattern as auth_required)
            try:
                directory = discord_directory()

                if directory is None or not directory.is_ready():
                    logger.debug("Discord directory not available")
                    return jsonify({"message": "Discord bot not available"}), 503

                logger.debug("Checking if user is member of guild")

                is_member = directory.check_user_membership(int(user_discord_id), int(organization.guild_id))
                if not is_member:
                    logger.debug("User is not a member of guild")
                    return jsonify(
                        {"message": "You must be a member of this organization to access this resource"}
                    ), 403

                logger.debug(f"User is a member of {organization.name}")

                # Add user info and organization to kwargs for the wrapped function
                kwargs["user_discord_id"] = user_discord_id
                kwargs["organization"] = organization

                logger.debug("Member authentication successful!")
                return f(*args, **kwargs)

            except Exception:
                # Log full exception details server-side without exposing them to the client
                logger.exception("Error checking guild membership")
                return jsonify({"message": "Error verifying membership"}), 500

        except Exception:
            # Log full exception details server-side without exposing them to the client
            logger.exception("General error in member_required")
            return jsonify({"message": "Internal server error"}), 500

    return wrapper


def error_handler(f):
    """
    Decorator to handle errors and return JSON error responses.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}")
            return jsonify({"error": str(e)}), 500

    return wrapper
