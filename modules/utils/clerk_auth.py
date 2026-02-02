import os
from functools import wraps
from flask import request, jsonify
from clerk_backend_api import Clerk
import httpx
from shared import config
from modules.utils.logging_config import get_logger

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
            headers={'Authorization': f'Bearer {token}'}
        )
        
        # Use Clerk's authenticate_request to verify the token
        if authorized_parties_env:
            authorized_parties = [
                party.strip()
                for party in authorized_parties_env.split(',')
                if party.strip()
            ]
        else:
            authorized_parties = ['http://localhost:3000', 'http://localhost:5173']
        
        request_state = clerk.authenticate_request(
            req,
            options={'authorized_parties': authorized_parties}
        )
        if not request_state.is_signed_in:
            logger.warning(f"Token invalid. Reason: {request_state.reason}")
            return None
        
        # Extract email from the payload
        payload = request_state.payload
        logger.debug(f"Token payload: {payload}")
        
        # Try to get email from various possible fields in Clerk token
        email = None
        if payload:
            email = (
                payload.get('email') or
                payload.get('email_address') or
                payload.get('primary_email_address_id')
            )
        
        if not email:
            logger.warning("No email found in token payload")
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
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No valid authorization header', 'message': 'Token is invalid!'}), 401
        
        # Safely extract token after 'Bearer '
        parts = auth_header.split(' ', 1)
        if len(parts) < 2 or not parts[1].strip():
            return jsonify({'error': 'No valid authorization header', 'message': 'Token is invalid!'}), 401
        
        token = parts[1].strip()
        
        # Verify token
        email = verify_clerk_token(token)
        
        if not email:
            return jsonify({'error': 'Invalid token', 'message': 'Token is invalid!'}), 401
        
        # Add user email to request context
        request.clerk_user_email = email
        
        return f(*args, **kwargs)
    
    return decorated_function
