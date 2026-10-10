"""Per-organization secrets (API tokens an org brings for its own integrations), encrypted at rest.

Modules declare the secrets they read with declare(). Values are encrypted with Fernet using
SECRETS_KEY; to rotate, put the new key first and keep the old one after a comma until every
secret has been saved again. Without SECRETS_KEY, secrets cannot be saved and reads return None,
so callers fall back to the instance-wide setting. The API never returns a secret's value.
"""

import os
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from core.base import Base
from core.logging_config import get_logger

logger = get_logger("secrets")

# name -> description, filled by the modules that read them
KNOWN: dict[str, str] = {}


class SecretsError(ValueError):
    pass


class OrgSecret(Base):
    __tablename__ = "org_secrets"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    ciphertext = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_by = Column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_secret_name"),)


def declare(name: str, description: str) -> None:
    KNOWN[name] = description


def _fernet() -> MultiFernet | None:
    keys = [k.strip() for k in os.environ.get("SECRETS_KEY", "").split(",") if k.strip()]
    if not keys:
        return None
    return MultiFernet([Fernet(k) for k in keys])


def configured() -> bool:
    return _fernet() is not None


def set_secret(db, org_id: int, name: str, value: object, updated_by: str | None = None) -> None:
    """Encrypt and store a secret. Commits."""
    if name not in KNOWN:
        raise SecretsError(f"Unknown secret: {name}")
    if not isinstance(value, str) or not value.strip():
        raise SecretsError("Value must be a non-empty string")
    fernet = _fernet()
    if fernet is None:
        raise SecretsError("SECRETS_KEY is not configured on this server")
    ciphertext = fernet.encrypt(value.strip().encode()).decode()
    row = db.query(OrgSecret).filter_by(organization_id=org_id, name=name).first()
    if row is None:
        row = OrgSecret(organization_id=org_id, name=name)
        db.add(row)
    row.ciphertext = ciphertext
    row.updated_at = datetime.now(UTC)
    row.updated_by = updated_by
    db.commit()


def get_secret(db, org_id: int, name: str) -> str | None:
    """The decrypted value, or None if unset, undecryptable, or SECRETS_KEY is missing."""
    row = db.query(OrgSecret).filter_by(organization_id=org_id, name=name).first()
    if row is None:
        return None
    fernet = _fernet()
    if fernet is None:
        logger.warning("secret %s is set for org %s but SECRETS_KEY is missing", name, org_id)
        return None
    try:
        return fernet.decrypt(str(row.ciphertext).encode()).decode()
    except InvalidToken:
        logger.error("secret %s for org %s cannot be decrypted with SECRETS_KEY", name, org_id)
        return None


def delete_secret(db, org_id: int, name: str) -> bool:
    row = db.query(OrgSecret).filter_by(organization_id=org_id, name=name).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def list_secrets(db, org_id: int) -> list[dict]:
    """Every declared secret and whether this org has set it. Never includes values."""
    rows = {row.name: row for row in db.query(OrgSecret).filter_by(organization_id=org_id).all()}
    return [
        {
            "name": name,
            "description": description,
            "set": name in rows,
            "updated_at": rows[name].updated_at.isoformat() if name in rows else None,
            "updated_by": rows[name].updated_by if name in rows else None,
        }
        for name, description in sorted(KNOWN.items())
    ]
