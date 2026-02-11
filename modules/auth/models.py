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
    created_at = Column(DateTime, default=func.utcnow())

    def __repr__(self):
        return f"<RefreshToken {self.token[:8]}...>"
