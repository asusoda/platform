"""GPU and CPU pods an org runs for its members, and the SSH keys its pods trust."""

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from core.db import Base, new_uuid
from core.time import utcnow


class ComputePod(Base):
    __tablename__ = "compute_pods"

    id = Column(String(36), primary_key=True, default=new_uuid)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    pod_id = Column(String(64), nullable=False)  # the provider's id
    # The hosting provider the pod runs on, a name in core.hosting.PROVIDERS
    provider = Column(String(32), nullable=False, default="runpod", server_default="runpod")
    name = Column(String(100), nullable=False)
    is_public = Column(Boolean, nullable=False, default=False)  # any member of the org may connect
    allowed_users = Column(JSON, nullable=False, default=list)  # Discord ids that may connect
    config = Column(JSON, nullable=False, default=dict)  # the create request, without secrets
    created_by = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "pod_id", name="uq_compute_pod"),)


class ComputeKey(Base):
    """An org's SSH key pairs. backend: root on its pods. user_ca: signs member certificates."""

    __tablename__ = "compute_keys"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    kind = Column(String(20), nullable=False)
    public_key = Column(Text, nullable=False)
    private_key = Column(Text, nullable=False)  # encrypted with SECRETS_KEY
    created_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "kind", name="uq_compute_key"),)


class ComputeSession(Base):
    """A time window when a pod should run, such as a workshop. The schedule job starts and stops it."""

    __tablename__ = "compute_sessions"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    pod_id = Column(String(64), nullable=False)  # RunPod's id
    title = Column(String(200), nullable=True)
    start_at = Column(DateTime, nullable=False)  # UTC
    stop_at = Column(DateTime, nullable=False)  # UTC
    started = Column(Boolean, nullable=False, default=False)  # the session began while the job was watching
    finished = Column(Boolean, nullable=False, default=False)  # the window has passed and was handled
    created_by = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (Index("ix_compute_sessions_due", "finished", "start_at"),)


class ComputeConnection(Base):
    """A certificate issued to a member or officer for one pod. Rows older than KEEP_DAYS are deleted on write."""

    __tablename__ = "compute_connections"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    pod_id = Column(String(64), nullable=False)  # RunPod's id
    discord_id = Column(String(32), nullable=False)
    username = Column(String(32), nullable=False)  # the user folder on the pod
    is_admin = Column(Boolean, nullable=False, default=False)  # a root certificate
    created_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (Index("ix_compute_connections_pod", "organization_id", "pod_id", "created_at"),)
