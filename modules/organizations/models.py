from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class Organization(Base):
    """Model representing a Discord organization/guild."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # URL-friendly prefix for the organization
    prefix: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)

    guild_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500))
    icon_url: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)  # Store organization-specific settings
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    # Changed to String since Discord role IDs are strings
    officer_role_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Calendar-related fields
    # Google Calendar ID for this org
    google_calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Notion database ID for this org
    notion_database_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Whether calendar sync is enabled
    calendar_sync_enabled: Mapped[bool | None] = mapped_column(Boolean, default=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # Last successful sync timestamp

    def __repr__(self):
        return f"<Organization(name='{self.name}', guild_id='{self.guild_id}')>"

    def to_dict(self):
        """Convert organization to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "guild_id": self.guild_id,
            "description": self.description,
            "icon_url": self.icon_url,
            "is_active": self.is_active,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "officer_role_id": self.officer_role_id,
            "google_calendar_id": self.google_calendar_id,
            "notion_database_id": self.notion_database_id,
            "calendar_sync_enabled": self.calendar_sync_enabled,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
        }
