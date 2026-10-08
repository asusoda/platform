"""Point entries. Members and memberships are in modules/users/models.py."""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.db import Base


class Points(Base):
    """Points one member got (or spent, when negative) in one org."""

    __tablename__ = "points"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    points = Column(Float, default=0.0)
    event = Column(String, nullable=True)
    awarded_by_officer = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    last_updated = Column(DateTime, default=lambda: datetime.now(UTC))
    user = relationship("User", back_populates="points")
    organization = relationship("Organization", backref="points")

    def __repr__(self):
        return f"<Points(id={self.id}, user_id={self.user_id}, organization_id={self.organization_id}, points={self.points}, event={self.event}, timestamp={self.timestamp})>"
