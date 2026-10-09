"""Members' connected accounts (OAuth grants) and logins in progress. Tokens are stored encrypted."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from core.db import Base, new_uuid
from core.time import utcnow


class AccountGrant(Base):
    __tablename__ = "account_grants"

    id = Column(String(36), primary_key=True, default=new_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id = Column(String(32), nullable=False)
    provider = Column(String(50), nullable=False)
    access_token = Column(Text, nullable=False)  # Fernet ciphertext
    refresh_token = Column(Text, nullable=True)  # Fernet ciphertext
    scopes = Column(Text, nullable=False, default="")  # space separated, as the provider granted
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "discord_id", "provider", name="uq_account_grant_owner"),)


class AccountLogin(Base):
    """A login an agent started for a member. One use; the browser must sign in to Discord as that member."""

    __tablename__ = "account_logins"

    state = Column(String(64), primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id = Column(String(32), nullable=False)
    provider = Column(String(50), nullable=False)
    verified_at = Column(DateTime, nullable=True)  # set once Discord confirmed the member
    created_at = Column(DateTime, nullable=False, default=utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (Index("ix_account_logins_expires_at", "expires_at"),)
