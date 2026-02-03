from modules.utils.base import Base
from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func


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
