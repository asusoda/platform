from flask import request, jsonify, Blueprint, redirect, current_app, session, url_for, make_response
from shared import config, bot, tokenManger
from modules.auth.decoraters import auth_required, error_handler
import requests

auth_blueprint = Blueprint("auth", __name__, template_folder=None, static_folder=None)
CLIENT_ID = config.CLIENT_ID
SECRET_KEY = config.CLIENT_SECRET
REDIRECT_URI = config.REDIRECT_URI
GUILD_ID = 762811961238618122


@auth_blueprint.route("/login", methods=["GET"])
def login():
    return redirect(
        f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds"
    )

@auth_blueprint.route("/validToken", methods=["GET"])
@auth_required
def validToken():
    token = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    if tokenManger.is_token_valid(token):
        return jsonify({"status": "success", "valid": True, "expired": False}), 200
    else:
        return jsonify({"status": "error", "valid": False}), 401

@auth_blueprint.route("/callback", methods=["GET"])
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No authorization code provided"}), 400
    token_response = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": SECRET_KEY,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_response_data = token_response.json()
    if "access_token" in token_response_data:
        access_token = token_response_data["access_token"]

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        user_response = requests.get(
            "https://discord.com/api/v10/users/@me", headers=headers
        )
        user_info = user_response.json()
        user_id = user_info["id"]
        if bot.check_officer(user_id):
            name = bot.get_name(user_id)
            code = tokenManger.generate_token(username=name)
            # Store user info in session
            session['user'] = {
                'username': name,
                'discord_id': user_id,
                'role': 'admin'  # Set role as admin for officers
            }
            session['token'] = code
            # Redirect to SuperAdmin dashboard and set token as cookie
            resp = make_response(redirect(url_for('superadmin_views.dashboard')))
            resp.set_cookie('soda_session_token', code, httponly=True, samesite='Lax')
            return resp
        else:
            full_url = f"{config.CLIENT_URL}/auth/?error=Unauthorized Access"
            return redirect(full_url)
    else:
        return jsonify({"error": "Failed to retrieve access token"}), 400


@auth_blueprint.route("/validateToken", methods=["GET"])
def valid_token():
    token = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    if tokenManger.is_token_valid(token):
        if tokenManger.is_token_expired(token):
            return jsonify(
                {
                    "status": "success",
                    "valid": True,
                    "expired": True,
                }
            ), 403
        else:
            return jsonify(
                {
                    "status": "success",
                    "valid": True,
                    "expired": False,
                }
            ), 200
    else:
        return jsonify(
            {
                "status": "error",
                "valid": False,
            }
        ), 401


@auth_blueprint.route("/refresh", methods=["GET"])
def refresh_token():
    token = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    if tokenManger.is_token_valid(token):
        if tokenManger.is_token_expired(token):
            new_token = tokenManger.refresh_token(token)
            return jsonify(
                {
                    "status": "success",
                    "valid": True,
                    "expired": True,
                    "token": new_token,
                }
            ), 200
        else:
            return jsonify(
                {
                    "status": "success",
                    "valid": True,
                    "expired": False,
                    "token": token,
                    "error": "Token is not expired",
                }
            ), 400
    else:
        return jsonify(
            {"status": "error", "valid": False, "error": "Invalid token"}
        ), 401


@auth_blueprint.route("/appToken", methods=["GET"])
@auth_required
@error_handler
def generate_app_token():
    token = request.headers.get("Authorization").split(" ")[1]
    appname = request.args.get("appname")
    app_token = tokenManger.generate_app_token(
        tokenManger.retrieve_username(token), appname
    )
    return jsonify({"app_token": app_token}), 200


@auth_blueprint.route("/name", methods=["GET"])
@auth_required
def get_name():
    autorisation = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    return jsonify({"name": tokenManger.retrieve_username(autorisation)}), 200


@auth_blueprint.route("/logout", methods=["GET"])
@auth_required
def logout():
    token = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    tokenManger.delete_token(token)
    return jsonify({"message": "Logged out"}), 200


@auth_blueprint.route("/success")
def success():
    return "You have successfully logged in with Discord!"
