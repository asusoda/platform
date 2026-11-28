"""Sub-modules: parts of a module with their own switch, in modules/<module>/submodules/<name>/. No Flask here.

Each sub-module folder sets SUBMODULE in its __init__.py. modules/manifest.py lists the folders and loads them.
The switch key of a sub-module is <module>.<name>, such as points.store. A sub-module is on only when its module
is on too.

A shared sub-module, such as knowledge.asu, holds content made once for every org. It has one row in the
submodules table (SharedContent), and each org that has its switch on has a SubmoduleSubscription row. Search
and feed presets join on the subscription rows. set_subscription() keeps them in step with the switch.
"""

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import ModuleType
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from core import limits
from core.db import Base
from core.errors import ServiceError
from core.time import utcnow


@dataclass(frozen=True)
class Submodule:
    """A part of a module that an org turns on or off on its own."""

    # The parent module, such as points
    module: str
    # The folder name, such as store
    name: str
    # The name the dashboard shows, such as Store
    title: str
    description: str
    # Content made once for every org, which each org subscribes to
    shared: bool = False
    # Runs when an org turns the sub-module on, with the session and the org id
    on_enable: Callable[[Session, int], None] | None = None

    @property
    def key(self) -> str:
        return f"{self.module}.{self.name}"


# Every loaded sub-module by key, and its package
SUBMODULES: dict[str, Submodule] = {}
_PACKAGES: dict[str, ModuleType] = {}
_LOADED: set[str] = set()


class SubmoduleError(RuntimeError):
    pass


class SharedError(ServiceError):
    """A shared sub-module that an org cannot subscribe to."""


def load(packages: list[str]) -> None:
    """Import each package, such as modules.points.submodules.store, and register its SUBMODULE once."""
    for package in packages:
        if package in _LOADED:
            continue
        loaded = importlib.import_module(package)
        found = getattr(loaded, "SUBMODULE", None)
        parts = package.split(".")
        if not isinstance(found, Submodule):
            raise SubmoduleError(f"{package} sets no SUBMODULE")
        if found.name != parts[-1] or found.module != parts[-3]:
            raise SubmoduleError(f"{package} declares {found.key}; the folder gives {parts[-3]}.{parts[-1]}")
        SUBMODULES[found.key] = found
        _PACKAGES[found.key] = loaded
        _LOADED.add(package)


def get(key: str) -> Submodule | None:
    return SUBMODULES.get(key)


def of(module: str) -> list[Submodule]:
    """The sub-modules of a module, in load order."""
    return [s for s in SUBMODULES.values() if s.module == module]


def shared() -> list[Submodule]:
    """The shared sub-modules of every module, in load order."""
    return [s for s in SUBMODULES.values() if s.shared]


def attribute(key: str, name: str, default: Any = None) -> Any:
    """A value that a sub-module's __init__.py sets next to SUBMODULE, such as FEEDS, or default."""
    package = _PACKAGES.get(key)
    return getattr(package, name, default) if package is not None else default


class SharedContent(Base):
    """One row for each shared sub-module. knowledge_sources.submodule_id points here for shared pages."""

    __tablename__ = "submodules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The sub-module key, such as knowledge.asu
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # code (a sub-module folder) or manifest (org-made)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="code")
    manifest: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    owner_org_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    # draft, pending, shared or retired
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="shared")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class SubmoduleSubscription(Base):
    """An org that has a shared sub-module on."""

    __tablename__ = "submodule_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submodule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("submodules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "submodule_id", name="uq_submodule_subscription"),)


def subscription_count(db, org_id: int) -> int:
    return db.query(SubmoduleSubscription).filter_by(organization_id=org_id).count()


SUBSCRIPTIONS_LIMIT = "submodules.subscriptions"
limits.declare(
    SUBSCRIPTIONS_LIMIT,
    "organizations",
    "Shared sub-modules",
    20,
    unit="subscriptions",
    usage=subscription_count,
)


def row_for(db, sub: Submodule) -> SharedContent:
    """The shared sub-module's row, made or brought up to date from its declaration. Flushes."""
    row = db.query(SharedContent).filter_by(key=sub.key).first()
    if row is None:
        row = SharedContent(key=sub.key, origin="code", status="shared")
        db.add(row)
    row.title, row.description = sub.title, sub.description
    db.flush()
    return row


def subscribed_keys(db, org_id: int) -> set[str]:
    """The keys of the shared sub-modules the org has a subscription row for."""
    rows = (
        db.query(SharedContent.key)
        .join(SubmoduleSubscription, SubmoduleSubscription.submodule_id == SharedContent.id)
        .filter(SubmoduleSubscription.organization_id == org_id)
        .all()
    )
    return {str(r[0]) for r in rows}


def set_subscription(db, org_id: int, sub: Submodule, on: bool, actor: str | None = None) -> None:
    """Add or delete the org's subscription row of a shared sub-module. Checks the limit on add. Does not commit."""
    row = row_for(db, sub)
    current = db.query(SubmoduleSubscription).filter_by(organization_id=org_id, submodule_id=row.id).first()
    if on and current is None:
        if row.status != "shared":
            raise SharedError(f"{sub.key} is not shared content", 409)
        limits.check(db, org_id, SUBSCRIPTIONS_LIMIT)
        db.add(SubmoduleSubscription(organization_id=org_id, submodule_id=row.id, created_by=actor))
    elif not on and current is not None:
        db.delete(current)
    db.flush()
