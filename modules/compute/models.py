"""GPU and CPU pods an org runs for its members, and the SSH keys its pods trust."""

import datetime
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from core.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class ComputePod(Base):
    __tablename__ = "compute_pods"

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    pod_id = Column(String(64), nullable=False)  # RunPod's id
    name = Column(String(100), nullable=False)
    is_public = Column(Boolean, nullable=False, default=False)  # any member of the org may connect
    allowed_users = Column(JSON, nullable=False, default=list)  # Discord ids that may connect
    config = Column(JSON, nullable=False, default=dict)  # the create request, without secrets
    created_by = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (UniqueConstraint("organization_id", "pod_id", name="uq_compute_pod"),)


class ComputeKey(Base):
    """An org's SSH key pairs. backend: root on its pods. user_ca: signs member certificates."""

    __tablename__ = "compute_keys"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    kind = Column(String(20), nullable=False)
    public_key = Column(Text, nullable=False)
    private_key = Column(Text, nullable=False)  # encrypted with SECRETS_KEY
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (UniqueConstraint("organization_id", "kind", name="uq_compute_key"),)
