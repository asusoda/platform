import os
import jwt
import requests
from functools import wraps, lru_cache
from flask import request, jsonify

CLERK_SECRET_KEY = os.environ.get('CLERK_SECRET_KEY')
CLERK_PUBLISHABLE_KEY = os.environ.get('NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY')

def get_clerk_frontend_api():
    """Extract frontend API URL from publishable key"""
    if not CLERK_PUBLISHABLE_KEY:
        return None
    try:
        # pk_test_xxx.clerk.accounts.dev$ -> lenient-slug-40.clerk.accounts.dev
        parts = CLERK_PUBLISHABLE_KEY.split('_')
        if len(parts) >= 3:
            domain_part = parts[2].rstrip('$')
            return f"https://{domain_part}"
    except (IndexError, AttributeError):
        pass
    return "https://lenient-slug-40.clerk.accounts.dev"

@lru_cache(maxsize=128)
def get_clerk_jwks():
    """Fetch Clerk JWKS (cached)"""
    frontend_api = get_clerk_frontend_api()
    if not frontend_api:
        return None
    
    try:
        jwks_url = f"{frontend_api}/.well-known/jwks.json"
        print(f"[Clerk Auth] Fetching JWKS from: {jwks_url}")
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[Clerk Auth] Failed to fetch JWKS: {e}")
        return None

def verify_clerk_token(token):
    """Verify Clerk JWT token and return user email"""
    try:
        if not token:
            return None
        
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')
        
        jwks = get_clerk_jwks()
        if not jwks or 'keys' not in jwks:
            print("[Clerk Auth] JWKS not available")
            return None
        
        # Find the key with matching kid
        public_key = None
        for key in jwks['keys']:
            if key.get('kid') == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break
        
        if not public_key:
            print(f"[Clerk Auth] Public key not found for kid: {kid}")
            return None
        
        # Verify and decode the token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            options={"verify_signature": True, "verify_exp": True}
        )
        
        print(f"[Clerk Auth] Token payload keys: {list(payload.keys())}")
        print(f"[Clerk Auth] Full payload: {payload}")
        
        # Extract email from Clerk token (try multiple possible fields)
        email = (
            payload.get('email') or 
            payload.get('email_address') or 
            payload.get('primary_email') or
            (payload.get('email_addresses', [{}])[0] if payload.get('email_addresses') else None)
        )
        
        if not email:
            print(f"[Clerk Auth] No email found in token. Available fields: {payload.keys()}")
            return None
        
        print(f"[Clerk Auth] Successfully verified token for: {email}")
        return email
        
    except jwt.ExpiredSignatureError:
        print("[Clerk Auth] Token expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"[Clerk Auth] Invalid token: {e}")
        return None
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
