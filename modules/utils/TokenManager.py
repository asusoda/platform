import datetime
import hashlib
import os
import secrets

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


class TokenManager:
    def __init__(self, algorithm="RS256", keys_path="./data") -> None:
        self.algorithm = algorithm
        self.keys_path = keys_path
        self.private_key_file = os.path.join(keys_path, "jwt_private.pem")
        self.public_key_file = os.path.join(keys_path, "jwt_public.pem")
        self.private_key, self.public_key = self.load_or_generate_keys()
        self.blacklist = set()
        self._db_connect = None

    def _get_db_connect(self):
        """Lazily import db_connect to avoid circular imports"""
        if self._db_connect is None:
            from shared import db_connect

            self._db_connect = db_connect
        return self._db_connect

    def _get_db_session(self):
        """Get a database session"""
        db_connect = self._get_db_connect()
        return db_connect.SessionLocal()

    @staticmethod
    def _hash_token(token):
        """Hash a refresh token using SHA-256 for secure storage"""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def load_or_generate_keys(self):
        """Load keys from disk if they exist, otherwise generate and save new ones"""
        # Check if both key files exist
        if os.path.exists(self.private_key_file) and os.path.exists(self.public_key_file):
            try:
                # Load existing keys
                with open(self.private_key_file, encoding="utf-8") as f:
                    private_key = f.read()
                with open(self.public_key_file, encoding="utf-8") as f:
                    public_key = f.read()
                logger.info(f"Loaded existing RSA keys from {self.keys_path}")
                return private_key, public_key
            except Exception as e:
                logger.error(f"Error loading keys: {e}. Generating new keys...")

        # Generate new keys if loading failed or files don't exist
        private_key, public_key = self.generate_keys()

        # Save keys to disk
        try:
            os.makedirs(self.keys_path, exist_ok=True)
            with open(self.private_key_file, "w") as f:
                f.write(private_key)
            with open(self.public_key_file, "w") as f:
                f.write(public_key)
            # Set restrictive permissions on private key
            os.chmod(self.private_key_file, 0o600)
            logger.info(f"Generated and saved new RSA keys to {self.keys_path}")
        except Exception as e:
            logger.warning(f"Could not save keys to disk: {e}")

        return private_key, public_key

    def generate_keys(self):
        """Generate a new RSA key pair"""
        # Generate a private RSA key
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # Generate the corresponding public key
        public_key = private_key.public_key()

        # Serialize private key to PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Serialize public key to PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return private_pem.decode("utf-8"), public_pem.decode("utf-8")

    def generate_token_pair(self, username, discord_id=None, access_exp_minutes=30, refresh_exp_days=7):
        """
        Generate both access token and refresh token.

        Args:
            username (str): The user's display name
            discord_id (str): The user's Discord ID (recommended for security)
            access_exp_minutes (int): Access token expiration time in minutes
            refresh_exp_days (int): Refresh token expiration time in days

        Returns:
            tuple: (access_token, refresh_token)
        """
        # Generate access token (short-lived)
        access_token = self.generate_token(username, discord_id, access_exp_minutes)

        # Generate refresh token (long-lived, stored securely)
        refresh_token = self.generate_refresh_token(username, discord_id, refresh_exp_days)

        return access_token, refresh_token

    def generate_token(self, username, discord_id=None, exp_minutes=60):
        """
        Generate a JWT token with username and optional discord_id.

        Args:
            username (str): The user's display name
            discord_id (str): The user's Discord ID (recommended for security)
            exp_minutes (int): Token expiration time in minutes

        Returns:
            str: JWT token
        """
        payload = {
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=exp_minutes),
            "username": username,
            "type": "access",  # Token type for security
        }

        # Add discord_id to payload if provided (more secure)
        if discord_id:
            payload["discord_id"] = str(discord_id)

        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def generate_refresh_token(self, username, discord_id=None, exp_days=7):
        """
        Generate a refresh token and store its hash in the database.

        Args:
            username (str): The user's display name
            discord_id (str): The user's Discord ID
            exp_days (int): Refresh token expiration time in days

        Returns:
            str: Refresh token (raw, returned only once)
        """
        from modules.auth.models import RefreshToken

        # Generate a cryptographically secure random token
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        expires_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + datetime.timedelta(days=exp_days)

        # Store hashed refresh token in database
        db = self._get_db_session()
        try:
            db_token = RefreshToken(
                token=token_hash,
                username=username,
                discord_id=str(discord_id) if discord_id else None,
                expires_at=expires_at,
            )
            db.add(db_token)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing refresh token: {e}")
            raise
        finally:
            db.close()

        return raw_token

    def refresh_access_token(self, refresh_token):
        """
        Generate a new access token using a valid refresh token.

        Args:
            refresh_token (str): The raw refresh token

        Returns:
            str: New access token, or None if refresh token is invalid
        """
        from modules.auth.models import RefreshToken

        token_hash = self._hash_token(refresh_token)
        db = self._get_db_session()
        try:
            db_token = db.query(RefreshToken).filter(RefreshToken.token == token_hash).first()

            if not db_token:
                return None

            # Check if refresh token is expired (both datetimes are UTC, compare as naive)
            expires_at = db_token.expires_at
            if expires_at.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=None)
            if datetime.datetime.now(datetime.UTC).replace(tzinfo=None) > expires_at:
                db.delete(db_token)
                db.commit()
                return None

            # Generate new access token
            new_access_token = self.generate_token(
                username=db_token.username,
                discord_id=db_token.discord_id,
                exp_minutes=30,
            )

            return new_access_token
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return None
        finally:
            db.close()

    def revoke_refresh_token(self, refresh_token):
        """
        Revoke a refresh token.

        Args:
            refresh_token (str): The raw refresh token to revoke

        Returns:
            bool: True if token was revoked, False if not found
        """
        from modules.auth.models import RefreshToken

        token_hash = self._hash_token(refresh_token)
        db = self._get_db_session()
        try:
            db_token = db.query(RefreshToken).filter(RefreshToken.token == token_hash).first()
            if db_token:
                db.delete(db_token)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error revoking refresh token: {e}")
            return False
        finally:
            db.close()

    def cleanup_expired_refresh_tokens(self):
        """
        Remove expired refresh tokens from the database.
        """
        from modules.auth.models import RefreshToken

        db = self._get_db_session()
        try:
            current_time = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
            deleted = db.query(RefreshToken).filter(RefreshToken.expires_at < current_time).delete()
            db.commit()
            if deleted:
                logger.info(f"Cleaned up {deleted} expired refresh tokens")
        except Exception as e:
            db.rollback()
            logger.error(f"Error cleaning up expired refresh tokens: {e}")
        finally:
            db.close()

    def retrieve_username(self, token):
        try:
            payload = jwt.decode(token, self.public_key, algorithms=[self.algorithm])
            return payload.get("username")
        except jwt.ExpiredSignatureError:
            try:
                payload = jwt.decode(
                    token,
                    self.public_key,
                    algorithms=[self.algorithm],
                    options={"verify_exp": False},
                )
                return payload.get("username")
            except jwt.DecodeError:
                return None

    def retrieve_discord_id(self, token):
        """
        Retrieve discord_id from JWT token.

        Args:
            token (str): JWT token

        Returns:
            str: Discord ID if present in token, None otherwise
        """
        try:
            payload = jwt.decode(token, self.public_key, algorithms=[self.algorithm])
            return payload.get("discord_id")
        except jwt.ExpiredSignatureError:
            try:
                payload = jwt.decode(
                    token,
                    self.public_key,
                    algorithms=[self.algorithm],
                    options={"verify_exp": False},
                )
                return payload.get("discord_id")
            except jwt.DecodeError:
                return None

    def decode_token(self, token):
        return jwt.decode(token, self.public_key, algorithms=[self.algorithm])

    def get_username_from_expiration(self, token):
        try:
            payload = jwt.decode(token, self.public_key, algorithms=[self.algorithm])
            return payload["username"]
        except jwt.InvalidTokenError:
            return None

    def is_token_valid(self, token):
        if token in self.blacklist:
            return False
        try:
            self.decode_token(token)
            return True
        except jwt.InvalidTokenError:
            return False

    def is_token_expired(self, token):
        try:
            self.decode_token(token)
            return False
        except jwt.ExpiredSignatureError:
            return True

    def refresh_token(self, token):
        username = self.retrieve_username(token)
        discord_id = self.retrieve_discord_id(token)
        return self.generate_token(username, discord_id)

    def generate_app_token(self, name, app_name):
        payload = {
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=120),
            "name": name,
            "app_name": app_name,
        }
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def delete_token(self, token):
        self.blacklist.add(token)
