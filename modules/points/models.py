"""Point entries and CSV import runs. Members and memberships are in modules/members/models.py."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Points(Base):
    """Points one member got (or spent, when negative) in one org."""

    __tablename__ = "points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    points: Mapped[float | None] = mapped_column(Float, default=0.0)
    event: Mapped[str | None] = mapped_column(String, nullable=True)
    awarded_by_officer: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    last_updated: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    user = relationship("User", back_populates="points")
    organization = relationship("Organization", backref="points")

    __table_args__ = (
        Index("ix_points_organization_id_user_id", "organization_id", "user_id"),
        Index("ix_points_user_id", "user_id"),
    )

    def __repr__(self):
        return f"<Points(id={self.id}, user_id={self.user_id}, organization_id={self.organization_id}, points={self.points}, event={self.event}, timestamp={self.timestamp})>"


class PointsImport(Base):
    """One run of an attendance CSV import: its progress, counts and the error of each failed row."""

    __tablename__ = "points_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(String(255), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    # queued, running, done or failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    rows_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # A list of {row, email, message}
    errors: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
