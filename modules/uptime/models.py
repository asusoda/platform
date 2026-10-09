"""Uptime monitors of an org and the result of each check."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from core.db import Base
from core.time import utcnow


class UptimeMonitor(Base):
    """One address that the org checks on a schedule: a public URL, or the health URL of a Hosting app."""

    __tablename__ = "uptime_monitors"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(100), nullable=False)
    target_kind = Column(String(16), nullable=False)  # url or app
    target = Column(String(500), nullable=False)  # the URL, or the name of an app in runpod_apps
    expected_status = Column(String(8), nullable=False, default="2xx")  # 2xx, or one status code such as 204
    timeout_seconds = Column(Integer, nullable=False, default=10)
    interval_minutes = Column(Integer, nullable=False, default=5)
    enabled = Column(Boolean, nullable=False, default=True)
    state = Column(String(8), nullable=True)  # up, down, or null before the first check
    state_since = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_uptime_monitor_name"),)


class UptimeCheck(Base):
    """One check of a monitor. The uptime.prune job deletes checks older than UPTIME_RETENTION_DAYS."""

    __tablename__ = "uptime_checks"

    id = Column(Integer, primary_key=True)
    monitor_id = Column(Integer, ForeignKey("uptime_monitors.id", ondelete="CASCADE"), nullable=False)
    checked_at = Column(DateTime, nullable=False, default=utcnow)
    up = Column(Boolean, nullable=False)
    status_code = Column(Integer, nullable=True)  # null when no response came back
    latency_ms = Column(Integer, nullable=True)
    error = Column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_uptime_checks_monitor", "monitor_id", "checked_at"),
        Index("ix_uptime_checks_checked_at", "checked_at"),
    )
