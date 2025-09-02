from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean, UniqueConstraint
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from modules.utils.base import Base

# Updated User model to support multiple organizations
# Updated User model to support multiple organizations
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, unique=True, index=True, nullable=True)  # Can be null for non-Discord users
    username = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    name = Column(String)
    asu_id = Column(String, unique=True, index=True, nullable=True)
    academic_standing = Column(String)
    major = Column(String)
    uuid = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    
    # Relationships
    points = relationship("Points", back_populates="user")
    orders = relationship("Order", back_populates="user")
    memberships = relationship("UserOrganizationMembership", back_populates="user")
    orders = relationship("Order", back_populates="user")
    memberships = relationship("UserOrganizationMembership", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, discord_id={self.discord_id}, username={self.username})>"

# New model to handle user-organization relationships

class UserOrganizationMembership(Base):
    __tablename__ = "user_organization_memberships"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", backref="memberships")
    
    # Unique constraint to prevent duplicate memberships
    __table_args__ = (UniqueConstraint('user_id', 'organization_id', name='unique_user_org'),)
    
    def __repr__(self):
        return f"<UserOrganizationMembership(user_id={self.user_id}, org_id={self.organization_id})>"

class Points(Base):
    __tablename__ = "points"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    points = Column(Float, default=0.0)
    event = Column(String, nullable=True)  # Event name/description
    awarded_by_officer = Column(String, nullable=True)  # Officer who awarded the points
    timestamp = Column(DateTime, default=datetime.utcnow)  # When points were awarded
    last_updated = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="points")
    organization = relationship("Organization", backref="points")

    def __repr__(self):
        return f"<Points(id={self.id}, user_id={self.user_id}, organization_id={self.organization_id}, points={self.points}, event={self.event}, timestamp={self.timestamp})>"
