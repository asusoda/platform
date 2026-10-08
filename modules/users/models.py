"""Members and their org memberships."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from core.db import Base


class User(Base):
    """A person. One row can be a member of many orgs."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, unique=True, index=True, nullable=True)
    username = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    name = Column(String)
    student_id = Column(String, unique=True, index=True, nullable=True)  # the school's student number
    class_standing = Column(String)  # freshman, senior, graduate and so on, as the org writes it
    major = Column(String)
    uuid = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    points = relationship("Points", back_populates="user")
    orders = relationship("Order", back_populates="user")
    memberships = relationship("UserOrganizationMembership", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, discord_id={self.discord_id}, username={self.username})>"


class UserOrganizationMembership(Base):
    """A user's membership in one org. A user has at most one row per org."""

    __tablename__ = "user_organization_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(UTC))
    is_active = Column(Boolean, default=True)
    # Fields the org defines for its members, such as major or shirt size
    profile_fields = Column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict, server_default=text("'{}'")
    )

    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", backref="memberships")

    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="unique_user_org"),)

    def __repr__(self):
        return f"<UserOrganizationMembership(user_id={self.user_id}, org_id={self.organization_id})>"
