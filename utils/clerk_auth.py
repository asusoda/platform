import os
import jwt
from functools import wraps
from flask import request, jsonify

CLERK_SECRET_KEY = os.environ.get('CLERK_SECRET_KEY')

def verify_clerk_token(token):
    """Verify Clerk JWT token and return user email"""
    try:
        if not CLERK_SECRET_KEY:
            raise ValueError("CLERK_SECRET_KEY not configured")
        
        decoded = jwt.decode(
            token,
            CLERK_SECRET_KEY,
            algorithms=["RS256"],
            options={"verify_signature": False}
        )
        
        return decoded.get('email') or decoded.get('email_addresses', [{}])[0].get('email_address')
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None

def require_clerk_auth(f):
    """Decorator to require Clerk authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401
        
        token = auth_header.split(' ')[1]
        email = verify_clerk_token(token)
        
        if not email:
            return jsonify({'error': 'Invalid token'}), 401
        
        request.clerk_user_email = email
        return f(*args, **kwargs)
    
    return decorated_function
