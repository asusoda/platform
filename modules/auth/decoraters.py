import functools
import logging
from functools import wraps

from flask import current_app, jsonify, request, session

from shared import config, tokenManger

logger = logging.getLogger(__name__)


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
                if not tokenManger.is_token_valid(session["token"]):
                    session.pop("token", None)
                    return jsonify({"message": "Session token is invalid!"}), 401
                elif tokenManger.is_token_expired(session["token"]):
                    session.pop("token", None)
                    return jsonify({"message": "Session token has expired!"}), 401
                return f(*args, **kwargs)
            except Exception:
                session.pop("token", None)
                return jsonify({"message": "Session authentication failed!"}), 401

        # If no session, check Authorization header (for API calls)
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return jsonify({"message": "Authentication required!"}), 401

        try:
            if not tokenManger.is_token_valid(token):
                logger.debug("Token is invalid")
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManger.is_token_expired(token):
                logger.debug("Token is expired")
                return jsonify({"message": "Token is expired!"}), 403
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"message": str(e)}), 401

    return wrapper


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
                if not tokenManger.is_token_valid(token):
                    logger.debug("Session token is invalid!")
                    return jsonify({"message": "Token is invalid!"}), 401
                elif tokenManger.is_token_expired(token):
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
            if not tokenManger.is_token_valid(token):
                logger.debug("API token is invalid!")
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManger.is_token_expired(token):
                logger.debug("API token is expired!")
                return jsonify({"message": "Token is expired!"}), 403

            logger.debug("API token is valid, decoding...")
            # For API calls, we need to verify superadmin status from the token
            token_data = tokenManger.decode_token(token)
            if not token_data:
                logger.debug("Failed to decode token data!")
                return jsonify({"message": "Invalid token data!"}), 401

            logger.debug("Token decoded successfully")

            # Try to get discord_id directly from token (more secure)
            discord_id = token_data.get("discord_id")
            if discord_id:
                logger.debug("Found discord_id in token")
                # Direct lookup using discord_id (secure and efficient)
                try:
                    # Get the auth bot from Flask app context
                    logger.debug("Getting auth bot from Flask app context...")
                    auth_bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
                    if not auth_bot:
                        logger.debug("Auth bot not found in Flask app context!")
                        return jsonify({"message": "Bot not available for verification!"}), 503

                    if not auth_bot.is_ready():
                        logger.debug("Auth bot is not ready!")
                        return jsonify({"message": "Bot not available for verification!"}), 503

                    logger.debug("Auth bot is ready, checking officer status...")
                    logger.debug("Checking if user is officer in any guild...")
                    officer_guilds = auth_bot.check_officer(str(discord_id), config.SUPERADMIN_USER_ID)
                    logger.debug(f"Officer guilds result: {bool(officer_guilds)}")

                    if not officer_guilds:  # If user is not officer in any organization
                        logger.debug("User is not an officer in any organization!")
                        return jsonify({"message": "Superadmin access required!"}), 403

                    logger.debug(f"User is an officer in {len(officer_guilds)} guild(s)!")
                except Exception as e:
                    logger.error(f"Error verifying superadmin status: {e}")
                    import traceback

                    traceback.print_exc()
                    return jsonify({"message": f"Error verifying superadmin status: {str(e)}"}), 401
            else:
                logger.debug("No discord_id in token, trying username lookup...")
                # Fallback to username lookup for older tokens (less secure)
                username = token_data.get("username")
                if not username:
                    logger.debug("Token missing both discord_id and username!")
                    return jsonify({"message": "Token missing user identification!"}), 401

                logger.debug("Using username for lookup")
                # Find the user's discord_id by looking through the bot's guild members
                # This is a reverse lookup: username -> discord_id (less secure)
                user_discord_id = None
                try:
                    # Get the auth bot from Flask app context
                    logger.debug("Getting auth bot for username lookup...")
                    auth_bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
                    if not auth_bot or not auth_bot.is_ready():
                        logger.debug("Auth bot not available for username lookup!")
                        return jsonify({"message": "Bot not available for verification!"}), 503

                    logger.debug("Searching through guild members for username")
                    for guild in auth_bot.guilds:
                        logger.debug(f"Checking guild: {guild.name}")
                        for member in guild.members:
                            display_name = member.nick if member.nick else member.name
                            if display_name == username:
                                user_discord_id = member.id
                                logger.debug(f"Found user in guild {guild.name}")
                                break
                        if user_discord_id:
                            break

                    if not user_discord_id:
                        logger.debug("User not found in any Discord guild!")
                        return jsonify({"message": "User not found in Discord!"}), 401

                    logger.debug("Checking officer status for user")
                    # Check if user is still an officer using the bot's check_officer method
                    officer_guilds = auth_bot.check_officer(str(user_discord_id))
                    logger.debug(f"Officer guilds result: {bool(officer_guilds)}")
                    if not officer_guilds:  # If user is not officer in any organization
                        logger.debug("User is not an officer in any organization!")
                        return jsonify({"message": "Superadmin access required!"}), 403

                    logger.debug(f"User is an officer in {len(officer_guilds)} guild(s)!")

                except Exception as e:
                    logger.error(f"Error in username lookup: {e}")
                    import traceback

                    traceback.print_exc()
                    return jsonify({"message": f"Error verifying superadmin status: {str(e)}"}), 401

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
                from shared import auth_bot

                if not auth_bot:
                    logger.debug("Discord bot not available")
                    return jsonify({"message": "Discord bot not available"}), 503

                logger.debug("Checking if user is member of guild")

                # Use bot's method to check membership
                is_member = auth_bot.check_user_membership(int(user_discord_id), int(organization.guild_id))
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
