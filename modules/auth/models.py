import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from modules.utils.base import Base


class Session(Base):
    """Session model for storing user sessions in the database"""

    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), unique=True, nullable=False)
    data = Column(JSON, nullable=False)
    expiry = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.utcnow())
    updated_at = Column(DateTime, default=func.utcnow(), onupdate=func.utcnow())

    def __repr__(self):
        return f"<Session {self.session_id}>"


class RefreshToken(Base):
    """Model for storing refresh tokens in the database so they persist across server restarts"""

    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=False)
    discord_id = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC).replace(tzinfo=None))

    def __repr__(self):
        return f"<RefreshToken {self.token[:8]}...>"


def _utcnow():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class RevokedToken(Base):
    """A revoked access or app token, kept until it would have expired anyway."""

    __tablename__ = "revoked_tokens"
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class AppToken(Base):
    """An app token an officer issued. A token whose row is missing or revoked is refused."""

    __tablename__ = "app_tokens"
    id = Column(Integer, primary_key=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    app_name = Column(String(255), nullable=False)
    discord_id = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
