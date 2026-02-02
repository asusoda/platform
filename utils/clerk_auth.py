import os
import jwt
import requests
from functools import wraps, lru_cache
from flask import request, jsonify

CLERK_SECRET_KEY = os.environ.get('CLERK_SECRET_KEY')
CLERK_PUBLISHABLE_KEY = os.environ.get('NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY')

@lru_cache(maxsize=1)
def get_clerk_jwks():
    """Fetch Clerk JWKS (cached)"""
    if not CLERK_PUBLISHABLE_KEY:
        return None
    
    # Extract instance ID from publishable key (pk_test_xxxxx-slug-40.clerk.accounts.dev$)
    try:
        jwks_url = f"https://api.clerk.dev/v1/jwks"
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch JWKS: {e}")
        return None

def verify_clerk_token(token):
    """Verify Clerk JWT token and return user email"""
    try:
        if not token:
            return None
        
        # Decode without verification first to get header
        unverified = jwt.decode(token, options={"verify_signature": False})
        
        # For now, just extract email without full verification
        # TODO: Implement proper JWKS verification
        email = (
            unverified.get('email') or 
            unverified.get('primary_email_address_id') or
            (unverified.get('email_addresses', [{}])[0].get('email_address') if unverified.get('email_addresses') else None)
        )
        
        if not email:
            # Try to get from public metadata
            public_metadata = unverified.get('public_metadata', {})
            email = public_metadata.get('email')
        
        print(f"[Clerk Auth] Decoded token for email: {email}")
        return email
    except Exception as e:
        print(f"[Clerk Auth] Token verification failed: {e}")
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
