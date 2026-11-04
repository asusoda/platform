"""GPU and CPU pods an org runs for its members, and the SSH keys its pods trust."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, new_uuid
from core.time import utcnow


class ComputePod(Base):
    __tablename__ = "compute_pods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    pod_id: Mapped[str] = mapped_column(String(64), nullable=False)  # the provider's id
    # The hosting provider the pod runs on, a name in core.hosting.PROVIDERS
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="runpod", server_default="runpod")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # any member of the org may connect
    allowed_users: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)  # Discord ids that may connect
    # the create request, without secrets
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    # Pod admin: officers may ask for root on this pod. The pod owner turns it on.
    admin_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    admin_enabled_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    admin_enabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The image the pod was created from, pinned by digest. A pod with no version predates the image check.
    image_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    image_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "pod_id", name="uq_compute_pod"),)


class ComputeKey(Base):
    """An org's SSH key pairs. backend: root on its pods. user_ca: signs member certificates."""

    __tablename__ = "compute_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    private_key: Mapped[str] = mapped_column(Text, nullable=False)  # encrypted with SECRETS_KEY
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "kind", name="uq_compute_key"),)


class ComputeSession(Base):
    """A time window when a pod should run, such as a workshop. The schedule job starts and stops it."""

    __tablename__ = "compute_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    pod_id: Mapped[str] = mapped_column(String(64), nullable=False)  # RunPod's id
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # UTC
    stop_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # UTC
    # the session began while the job was watching
    started: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # the window has passed and was handled
    finished: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (Index("ix_compute_sessions_due", "finished", "start_at"),)


class ComputeConnection(Base):
    """A certificate issued to a member or officer for one pod. Rows older than KEEP_DAYS are deleted on write."""

    __tablename__ = "compute_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    pod_id: Mapped[str] = mapped_column(String(64), nullable=False)  # RunPod's id
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)
    username: Mapped[str] = mapped_column(String(32), nullable=False)  # the user folder on the pod
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # a root certificate
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (Index("ix_compute_connections_pod", "organization_id", "pod_id", "created_at"),)


class ComputeCliCode(Base):
    """A one-time code from the CLI browser sign-in. The CLI redeems it with its PKCE verifier for a token."""

    __tablename__ = "compute_cli_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # SHA-256 hex of the code
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)  # S256
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)  # UTC
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
