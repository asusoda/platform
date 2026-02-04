import requests
from flask import Blueprint, current_app, jsonify, redirect, request, session

from modules.auth.decoraters import auth_required, error_handler
from modules.utils.logging_config import logger
from shared import config, tokenManager

auth_blueprint = Blueprint("auth", __name__, template_folder=None, static_folder=None)
CLIENT_ID = config.CLIENT_ID
CLIENT_SECRET = config.CLIENT_SECRET
REDIRECT_URI = config.REDIRECT_URI
GUILD_ID = 762811961238618122

logger.info(f"Auth API using CLIENT_ID: {CLIENT_ID} and REDIRECT_URI: {REDIRECT_URI}")


@auth_blueprint.route("/login", methods=["GET"])
def login():
    logger.info(f"Redirecting to Discord OAuth login for client_id: {CLIENT_ID} and REDIRECT_URI: {REDIRECT_URI}")
    return redirect(
        f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds"
    )


@auth_blueprint.route("/validToken", methods=["GET"])
@auth_required
def validToken():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"status": "error", "valid": False, "message": "No authorization header"}), 401
    token = auth_header.split(" ")[1]
    if tokenManager.is_token_valid(token):
        return jsonify({"status": "success", "valid": True, "expired": False}), 200
    else:
        return jsonify({"status": "error", "valid": False}), 401


@auth_blueprint.route("/callback", methods=["GET"])
def callback():
    # Get the auth bot from Flask app context (the one actually running in thread)
    auth_bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not auth_bot or not auth_bot.is_ready():  # type: ignore[attr-defined]
        logger.error("Auth bot is not available or not ready for /callback")
        return jsonify({"error": "Authentication service temporarily unavailable. Bot not ready."}), 503

    code = request.args.get("code")
    if not code:
        logger.warning("No authorization code provided in /callback")
        return jsonify({"error": "No authorization code provided"}), 400

    logger.info("Received authorization code, exchanging for token.")
    token_response = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,  # Add timeout to prevent hanging requests
    )
    token_response_data = token_response.json()

    if "access_token" in token_response_data:
        access_token = token_response_data["access_token"]
        logger.info("Access token received, fetching user info.")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        user_response = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=30)
        user_info = user_response.json()
        user_id = user_info["id"]
        officer_guilds = auth_bot.check_officer(user_id, config.SUPERADMIN_USER_ID)  # type: ignore[attr-defined]
        print(f"Officer guilds: {officer_guilds}")
        if officer_guilds:  # If user is officer in at least one organization
            name = auth_bot.get_name(user_id)  # type: ignore[attr-defined]
            # Generate token pair with both access and refresh tokens
            access_token, refresh_token = tokenManager.generate_token_pair(
                username=name, discord_id=user_id, access_exp_minutes=30, refresh_exp_days=7
            )
            # Store user info in session with officer guilds
            session["user"] = {
                "username": name,
                "discord_id": user_id,
                "role": "officer",
                "officer_guilds": officer_guilds,  # Store the list of guild IDs where user is officer
            }
            session["token"] = access_token
            session["refresh_token"] = refresh_token
            # Redirect to React frontend with both tokens
            frontend_url = f"{config.CLIENT_URL}/auth/?access_token={access_token}&refresh_token={refresh_token}"
            return redirect(frontend_url)
        else:
            full_url = f"{config.CLIENT_URL}/auth/?error=Unauthorized Access"
            return redirect(full_url)
    else:
        logger.error(f"Failed to retrieve access token from Discord: {token_response_data}")
        return jsonify({"error": "Failed to retrieve access token"}), 400


@auth_blueprint.route("/refresh", methods=["POST"])
def refresh_token():
    """
    Refresh access token using refresh token.
    """
    try:
        data = request.get_json()
        if not data or "refresh_token" not in data:
            return jsonify({"error": "Refresh token required"}), 400

        refresh_token = data["refresh_token"]

        # Generate new access token
        new_access_token = tokenManager.refresh_access_token(refresh_token)

        if new_access_token:
            return jsonify(
                {
                    "access_token": new_access_token,
                    "token_type": "Bearer",  # nosec B105 - OAuth2 token type, not a password
                    "expires_in": 1800,  # 30 minutes in seconds
                }
            ), 200
        else:
            return jsonify({"error": "Invalid or expired refresh token"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_blueprint.route("/revoke", methods=["POST"])
@auth_required
def revoke_token():
    """
    Revoke refresh token (logout).
    """
    try:
        data = request.get_json()
        if not data or "refresh_token" not in data:
            return jsonify({"error": "Refresh token required"}), 400

        refresh_token = data["refresh_token"]

        # Revoke the refresh token
        if tokenManager.revoke_refresh_token(refresh_token):
            # Also blacklist the current access token
            auth_header = request.headers.get("Authorization")
            if auth_header:
                current_token = auth_header.split(" ")[1]
                tokenManager.delete_token(current_token)

            return jsonify({"message": "Token revoked successfully"}), 200
        else:
            return jsonify({"error": "Invalid refresh token"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_blueprint.route("/validateToken", methods=["GET"])
def valid_token():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"status": "error", "valid": False, "message": "No authorization header"}), 401
    token = auth_header.split(" ")[1]
    if tokenManager.is_token_valid(token):
        if tokenManager.is_token_expired(token):
            logger.info("Token is valid but expired.")
            return jsonify({"status": "success", "valid": True, "expired": True}), 200
        else:
            logger.info("Token is valid and not expired.")
            return jsonify({"status": "success", "valid": True, "expired": False}), 200
    else:
        logger.warning("Token validation failed (invalid).")
        return jsonify({"status": "error", "valid": False, "message": "Token is invalid"}), 401


@auth_blueprint.route("/appToken", methods=["GET"])
@auth_required
@error_handler
def get_app_token():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "No authorization header"}), 401
    token = auth_header.split(" ")[1]
    appname = request.args.get("appname")
    if not appname:
        return jsonify({"error": "appname query parameter is required"}), 400

    username = tokenManager.retrieve_username(token)
    if not username:
        return jsonify({"error": "Invalid user token"}), 401

    logger.info(f"Generating app token for user {username}, app: {appname}")
    app_token_value = tokenManager.generate_app_token(username, appname)
    return jsonify({"app_token": app_token_value}), 200


@auth_blueprint.route("/name", methods=["GET"])
@auth_required
def get_name():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "No authorization header"}), 401
    autorisation = auth_header.split(" ")[1]

    return jsonify({"name": tokenManager.retrieve_username(autorisation)}), 200


@auth_blueprint.route("/logout", methods=["POST"])
def logout():
    """
    Logout endpoint that revokes refresh token.
    """
    try:
        data = request.get_json()
        if data and "refresh_token" in data:
            # Revoke refresh token
            tokenManager.revoke_refresh_token(data["refresh_token"])

        # Also blacklist current access token if provided
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]
            tokenManager.delete_token(token)

        # Clear session
        session.clear()

        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_blueprint.route("/success")
def success():
    return "You have successfully logged in with Discord! (This is a generic success page)"
