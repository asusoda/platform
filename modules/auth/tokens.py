"""Platform JWTs: access, refresh and app tokens, signed with an RSA key pair kept in ./data."""

import datetime
import hashlib
import os
import secrets

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from core.db import db_connect
from core.logging_config import get_logger
from modules.auth.models import AppToken, RefreshToken, RevokedToken

logger = get_logger(__name__)


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class TokenManager:
    def __init__(self, algorithm="RS256", keys_path="./data") -> None:
        self.algorithm = algorithm
        self.keys_path = keys_path
        self.private_key_file = os.path.join(keys_path, "jwt_private.pem")
        self.public_key_file = os.path.join(keys_path, "jwt_public.pem")
        self.private_key, self.public_key = self.load_or_generate_keys()
        # Revoked tokens this process has seen. The revoked_tokens table is the source of truth.
        self.blacklist = set()

    @staticmethod
    def _hash_token(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def load_or_generate_keys(self):
        """The key pair from disk. Makes and saves a new pair if the files are missing or unreadable."""
        if os.path.exists(self.private_key_file) and os.path.exists(self.public_key_file):
            try:
                with open(self.private_key_file, encoding="utf-8") as f:
                    private_key = f.read()
                with open(self.public_key_file, encoding="utf-8") as f:
                    public_key = f.read()
                logger.info(f"Loaded existing RSA keys from {self.keys_path}")
                return private_key, public_key
            except Exception as e:
                logger.error(f"Error loading keys: {e}. Generating new keys...")

        private_key, public_key = self.generate_keys()
        try:
            os.makedirs(self.keys_path, exist_ok=True)
            with open(self.private_key_file, "w") as f:
                f.write(private_key)
            with open(self.public_key_file, "w") as f:
                f.write(public_key)
            os.chmod(self.private_key_file, 0o600)
            logger.info(f"Generated and saved new RSA keys to {self.keys_path}")
        except Exception as e:
            logger.warning(f"Could not save keys to disk: {e}")

        return private_key, public_key

    def generate_keys(self):
        """A new RSA key pair as PEM strings (private, public)."""
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return private_pem.decode("utf-8"), public_pem.decode("utf-8")

    def generate_token_pair(self, username, discord_id=None, access_exp_minutes=30, refresh_exp_days=7):
        """A short-lived access token and a stored refresh token: (access_token, refresh_token)."""
        access_token = self.generate_token(username, discord_id, access_exp_minutes)
        refresh_token = self.generate_refresh_token(username, discord_id, refresh_exp_days)
        return access_token, refresh_token

    def generate_token(self, username, discord_id=None, exp_minutes=60):
        """An access token for the user."""
        payload = {
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=exp_minutes),
            "username": username,
            "type": "access",
        }
        if discord_id:
            payload["discord_id"] = str(discord_id)
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def generate_refresh_token(self, username, discord_id=None, exp_days=7):
        """A random refresh token. Only its hash is stored, so the raw value is returned once."""
        raw_token = secrets.token_urlsafe(32)
        db = db_connect.SessionLocal()
        try:
            db.add(
                RefreshToken(
                    token=self._hash_token(raw_token),
                    username=username,
                    discord_id=str(discord_id) if discord_id else None,
                    expires_at=_utcnow() + datetime.timedelta(days=exp_days),
                )
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing refresh token: {e}")
            raise
        finally:
            db.close()
        return raw_token

    def refresh_access_token(self, refresh_token):
        """A new access token for a stored, unexpired refresh token, else None."""
        db = db_connect.SessionLocal()
        try:
            db_token = db.query(RefreshToken).filter(RefreshToken.token == self._hash_token(refresh_token)).first()
            if not db_token:
                return None

            expires_at = db_token.expires_at
            if expires_at.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=None)
            if _utcnow() > expires_at:
                db.delete(db_token)
                db.commit()
                return None

            return self.generate_token(username=db_token.username, discord_id=db_token.discord_id, exp_minutes=30)
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return None
        finally:
            db.close()

    def revoke_refresh_token(self, refresh_token):
        """Delete a stored refresh token. True if it was found."""
        db = db_connect.SessionLocal()
        try:
            db_token = db.query(RefreshToken).filter(RefreshToken.token == self._hash_token(refresh_token)).first()
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
        """Remove expired refresh tokens, and revocations of tokens that have expired anyway."""
        db = db_connect.SessionLocal()
        try:
            now = _utcnow()
            deleted = db.query(RefreshToken).filter(RefreshToken.expires_at < now).delete()
            db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete()
            db.commit()
            if deleted:
                logger.info(f"Cleaned up {deleted} expired refresh tokens")
        except Exception as e:
            db.rollback()
            logger.error(f"Error cleaning up expired refresh tokens: {e}")
        finally:
            db.close()

    def _claims(self, token):
        """The token's claims, also when it has expired. None if an expired token does not decode."""
        try:
            return jwt.decode(token, self.public_key, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            try:
                return jwt.decode(token, self.public_key, algorithms=[self.algorithm], options={"verify_exp": False})
            except jwt.DecodeError:
                return None

    def retrieve_username(self, token):
        claims = self._claims(token)
        return claims.get("username") if claims else None

    def retrieve_discord_id(self, token):
        claims = self._claims(token)
        return claims.get("discord_id") if claims else None

    def decode_token(self, token):
        return jwt.decode(token, self.public_key, algorithms=[self.algorithm])

    def is_token_valid(self, token):
        if token in self.blacklist:
            return False
        try:
            claims = self.decode_token(token)
        except jwt.InvalidTokenError:
            return False
        return not self._is_revoked(token, claims)

    def _is_revoked(self, token, claims):
        """Revocations live in the database so they survive restarts and are shared by every process."""
        db = db_connect.SessionLocal()
        try:
            if db.query(RevokedToken.id).filter(RevokedToken.token_hash == self._hash_token(token)).first():
                self.blacklist.add(token)
                return True
            if claims.get("type") == "app" and claims.get("jti"):
                app_token = db.query(AppToken).filter(AppToken.jti == claims["jti"]).first()
                if app_token is None or app_token.revoked_at is not None:
                    return True
            return False
        finally:
            db.close()

    def is_token_expired(self, token):
        try:
            self.decode_token(token)
            return False
        except jwt.ExpiredSignatureError:
            return True

    def generate_app_token(self, name, app_name, discord_id=None):
        """A 120-day app token, recorded so officers can list and revoke it.

        With discord_id, the token names the issuing officer and is scoped to that officer's orgs.
        """
        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=120)
        jti = secrets.token_urlsafe(16)
        payload = {
            "exp": expires_at,
            "name": name,
            "app_name": app_name,
            "type": "app",
            "jti": jti,
        }
        if discord_id:
            payload["discord_id"] = str(discord_id)

        db = db_connect.SessionLocal()
        try:
            db.add(
                AppToken(
                    jti=jti,
                    name=name,
                    app_name=app_name,
                    discord_id=str(discord_id) if discord_id else None,
                    expires_at=expires_at.replace(tzinfo=None),
                )
            )
            db.commit()
        finally:
            db.close()
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def delete_token(self, token):
        """Revoke a token until it expires, for every process and across restarts."""
        self.blacklist.add(token)
        try:
            claims = jwt.decode(token, self.public_key, algorithms=[self.algorithm], options={"verify_exp": False})
        except jwt.InvalidTokenError:
            return
        expires_at = datetime.datetime.fromtimestamp(claims.get("exp", 0), datetime.UTC).replace(tzinfo=None)
        token_hash = self._hash_token(token)
        db = db_connect.SessionLocal()
        try:
            if not db.query(RevokedToken.id).filter(RevokedToken.token_hash == token_hash).first():
                db.add(RevokedToken(token_hash=token_hash, expires_at=expires_at))
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing token revocation: {e}")
        finally:
            db.close()


token_manager = TokenManager()
