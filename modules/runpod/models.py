"""Apps deployed to RunPod pods, and their deployments."""

import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from core.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class App(Base):
    __tablename__ = "runpod_apps"

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(63), nullable=False)
    manifest = Column(Text, nullable=False)  # JSON, validated by service.MANIFEST_SCHEMA
    pod_id = Column(String(64), nullable=True)  # set by the first deploy
    current_tag = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_runpod_app_name"),)


class AppDeployment(Base):
    __tablename__ = "runpod_deployments"

    id = Column(String(36), primary_key=True, default=_uuid)
    app_id = Column(String(36), ForeignKey("runpod_apps.id", ondelete="CASCADE"), nullable=False)
    tag = Column(String(128), nullable=False)
    status = Column(String(20), nullable=False)  # deploying, healthy, failed
    actor = Column(String(255), nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=_now)
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_runpod_deployments_app", "app_id", "started_at"),
        Index("ix_runpod_deployments_status", "status"),
    )
