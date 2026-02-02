import os
import jwt
import requests
import time
from functools import wraps
from flask import request, jsonify

CLERK_SECRET_KEY = os.environ.get('CLERK_SECRET_KEY')
CLERK_PUBLISHABLE_KEY = os.environ.get('NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY')
CLERK_FRONTEND_API_URL = os.environ.get('CLERK_FRONTEND_API_URL')

# Cache for JWKS with TTL
_jwks_cache = {'data': None, 'timestamp': 0}
_jwks_cache_ttl = 3600  # 1 hour TTL for JWKS cache

def get_clerk_frontend_api():
    """Extract frontend API URL from publishable key or use configured URL"""
    # Use explicitly configured URL if available
    if CLERK_FRONTEND_API_URL:
        return CLERK_FRONTEND_API_URL
    
    if not CLERK_PUBLISHABLE_KEY:
        return None
    try:
        # pk_test_xxx.clerk.accounts.dev$ -> lenient-slug-40.clerk.accounts.dev
        parts = CLERK_PUBLISHABLE_KEY.split('_')
        if len(parts) >= 3:
            domain_part = parts[2].rstrip('$')
            return f"https://{domain_part}"
    except (IndexError, AttributeError):
        # If parsing the publishable key fails, fall back to the default frontend API URL below.
        pass
    
    # Raise error if we can't determine the URL
    raise ValueError(
        "Cannot determine Clerk Frontend API URL. "
        "Please set CLERK_FRONTEND_API_URL environment variable, "
        "or ensure NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is properly formatted."
    )

def get_clerk_jwks():
    """Fetch Clerk JWKS with TTL-based caching to handle key rotation"""
    global _jwks_cache
    
    current_time = time.time()
    
    # Return cached JWKS if still valid
    if _jwks_cache['data'] and (current_time - _jwks_cache['timestamp']) < _jwks_cache_ttl:
        return _jwks_cache['data']
    
    # Fetch fresh JWKS
    try:
        frontend_api = get_clerk_frontend_api()
        if not frontend_api:
            return None
        
        jwks_url = f"{frontend_api}/.well-known/jwks.json"
        print(f"[Clerk Auth] Fetching JWKS from: {jwks_url}")
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        
        # Update cache
        _jwks_cache['data'] = response.json()
        _jwks_cache['timestamp'] = current_time
        
        return _jwks_cache['data']
    except Exception as e:
        print(f"[Clerk Auth] Failed to fetch JWKS: {e}")
        # Return stale cache if available as fallback
        if _jwks_cache.get('data'):
            print("[Clerk Auth] Using stale JWKS cache as fallback")
            return _jwks_cache['data']
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
        
        # Log only non-sensitive metadata for debugging
        if os.environ.get('DEBUG_CLERK_AUTH'):
            print(f"[Clerk Auth] Token payload keys: {list(payload.keys())}")
        
        # Extract email from Clerk token (try multiple possible fields)
        email = None
        
        # Try direct email fields first
        email = payload.get('email') or payload.get('email_address') or payload.get('primary_email')
        
        # If not found, try email_addresses array
        if not email and payload.get('email_addresses'):
            email_addresses = payload.get('email_addresses')
            if isinstance(email_addresses, list) and len(email_addresses) > 0:
                # Extract email_address field from first element
                first_email = email_addresses[0]
                if isinstance(first_email, dict):
                    email = first_email.get('email_address')
                elif isinstance(first_email, str):
                    email = first_email
        
        if not email:
            print(f"[Clerk Auth] No email found in token. Available fields: {list(payload.keys())}")
            return None
        
        # Only log email in debug mode to protect privacy
        if os.environ.get('DEBUG_CLERK_AUTH'):
            print(f"[Clerk Auth] Successfully verified token for: {email}")
        else:
            print(f"[Clerk Auth] Successfully verified token")
        
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
