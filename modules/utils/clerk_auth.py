from functools import wraps

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from flask import jsonify, request

from modules.utils.logging_config import get_logger
from shared import config

logger = get_logger("utils.clerk_auth")

_clerk_client = None

clerk_secret = config.CLERK_SECRET_KEY
authorized_parties_env = config.CLERK_AUTHORIZED_PARTIES


def get_clerk_client():
    """Get initialized Clerk client"""
    global _clerk_client
    if _clerk_client is None:
        _clerk_client = Clerk(bearer_auth=clerk_secret)
    return _clerk_client


def verify_clerk_token(token):
    """Verify Clerk session token using official SDK"""
    try:
        clerk = get_clerk_client()

        # Create an httpx.Request object with the Authorization header
        req = httpx.Request(
            method="GET",
            url="https://api.clerk.com/v1",  # URL doesn't matter for token verification
            headers={"Authorization": f"Bearer {token}"},
        )

        # Use Clerk's authenticate_request to verify the token
        if authorized_parties_env:
            authorized_parties = [party.strip() for party in authorized_parties_env.split(",") if party.strip()]
        else:
            authorized_parties = ["http://localhost:3000", "http://localhost:5173"]

        request_state = clerk.authenticate_request(
            req, AuthenticateRequestOptions(authorized_parties=authorized_parties)
        )
        if not request_state.is_signed_in:
            logger.warning(f"Token invalid. Reason: {request_state.reason}")
            return None
        # Extract basic payload for debugging
        payload = request_state.payload
        logger.debug(f"Token payload: {payload}")
        # Clerk tokens typically contain a user ID (sub) rather than an email.
        # Prefer request_state.user_id, fall back to sub in the payload if needed.
        user_id = getattr(request_state, "user_id", None) or (payload.get("sub") if payload else None)
        if not user_id:
            logger.warning("No user_id found in request state or token payload")
            return None
        try:
            user = clerk.users.get(user_id=user_id)
        except Exception as e:
            logger.error(f"Failed to fetch Clerk user for id {user_id}: {e}")
            return None
        # Resolve the primary email address from the user object
        email = None
        primary_email_id = getattr(user, "primary_email_address_id", None)
        email_addresses = getattr(user, "email_addresses", []) or []
        if primary_email_id:
            for addr in email_addresses:
                # addr may be a dict-like object or have attributes; support both.
                addr_id = addr.get("id") if isinstance(addr, dict) else getattr(addr, "id", None)
                if addr_id == primary_email_id:
                    email = (
                        addr.get("email_address") if isinstance(addr, dict) else getattr(addr, "email_address", None)
                    )
                    break
        # Fallback: use the first listed email address if no primary match was found
        if not email and email_addresses:
            first = email_addresses[0]
            email = first.get("email_address") if isinstance(first, dict) else getattr(first, "email_address", None)
        if not email:
            logger.warning("No email address could be resolved for user")
            return None

        logger.info(f"Successfully verified token for: {email}")
        return email

    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None


def require_clerk_auth(f):
    """Decorator to require Clerk authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "No valid authorization header", "message": "Clerk: Token is invalid!"}), 401

        # Safely extract token after 'Bearer '
        parts = auth_header.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            return jsonify({"error": "No valid authorization header", "message": "Clerk: Token is invalid!"}), 401

        token = parts[1].strip()

        # Verify token
        email = verify_clerk_token(token)

        if not email:
            return jsonify({"error": "Invalid token", "message": "Token is invalid!"}), 401

        # Add user email to request context
        request.clerk_user_email = email

        return f(*args, **kwargs)

    return decorated_function
