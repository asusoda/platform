"""Apps deployed to pods on a hosting provider, and their deployments."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from core.db import Base, new_uuid
from core.time import utcnow


class App(Base):
    __tablename__ = "runpod_apps"

    id = Column(String(36), primary_key=True, default=new_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(63), nullable=False)
    # The hosting provider the app runs on, a name in core.hosting.PROVIDERS
    provider = Column(String(32), nullable=False, default="runpod", server_default="runpod")
    manifest = Column(Text, nullable=False)  # JSON, validated by service.MANIFEST_SCHEMA
    repo = Column(String(201), nullable=True)  # owner/name whose manifest file is read on each deploy
    manifest_path = Column(String(200), nullable=True)
    pod_id = Column(String(64), nullable=True)  # set by the first deploy
    current_tag = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_runpod_app_name"),)


class AppDeployment(Base):
    __tablename__ = "runpod_deployments"

    id = Column(String(36), primary_key=True, default=new_uuid)
    app_id = Column(String(36), ForeignKey("runpod_apps.id", ondelete="CASCADE"), nullable=False)
    tag = Column(String(128), nullable=False)
    status = Column(String(20), nullable=False)  # deploying, healthy, failed
    actor = Column(String(255), nullable=True)
    manifest = Column(Text, nullable=True)  # JSON the deploy used, so a rollback reuses it
    manifest_ref = Column(String(100), nullable=True)  # git ref the manifest was read at
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=utcnow)
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_runpod_deployments_app", "app_id", "started_at"),
        Index("ix_runpod_deployments_status", "status"),
    )
