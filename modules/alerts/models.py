"""The org's destinations and the log of every message that Platform sent or tried to send to one."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.time import utcnow


class Destination(Base):
    """One destination of an org and the events it gets. The URL is encrypted with SECRETS_KEY."""

    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    url_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    url_hint: Mapped[str] = mapped_column(String(100), nullable=False)
    events: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_webhook_name"),)


class Delivery(Base):
    """One message that Platform sent or tried to send for an org: an event, a feed item, a test or a LeetCode post."""

    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    # Null for a bot post, a feed's older webhook secret, or a destination deleted since
    destination_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("webhooks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # event, feed, leetcode or test
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # The event key, the feed key or the LeetCode scope
    ref: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # sent or failed
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, index=True)

    __table_args__ = (Index("ix_deliveries_org_created", "organization_id", "created_at"),)
