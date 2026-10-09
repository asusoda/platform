"""Organization logic shared by the REST API, the bot and jobs. No Flask here."""

import re
from typing import cast
from urllib.parse import urlparse

from sqlalchemy.orm.attributes import flag_modified

from core import secrets
from core.errors import ServiceError
from modules.auth import machine_tokens, scopes
from modules.organizations.models import Organization

scopes.declare("org:read", "Read the org's name, description and enabled modules")
scopes.declare("settings:write", "Turn modules on or off, change branding, and resolve notifications")

# Modules an organization can turn off. Everything else (auth, users, organizations,
# superadmin, public pages) is always on. A module missing from an org's config is on,
# so existing orgs keep every feature until an officer turns one off.
OPTIONAL_MODULES = {
    "points": "Points, leaderboards and event check-ins",
    "storefront": "Merch store paid with points",
    "calendar": "Notion to Google Calendar sync and the public events feed",
    "leetcode": "Daily LeetCode post in the org's channel, with solve checks",
    "compute": "GPU and CPU pods on the org's RunPod account that members SSH into",
    "alerts": "Job and hackathon listings posted to Discord webhooks",
}


class ModuleError(ValueError):
    pass


class OrganizationError(ValueError):
    pass


class BrandingError(ServiceError, ValueError):
    pass


PREFIX_PATTERN = re.compile(r"^[a-z0-9_-]{2,20}$")
ACCENT_PATTERN = re.compile(r"#[0-9a-fA-F]{6}")
BRANDING_KEYS = ("logo_url", "accent_color", "website_url")
MAX_URL = 500


def find_by_prefix(db, prefix: str | None, *, active_only: bool = False) -> Organization | None:
    """The org with this prefix, or None. With active_only, an inactive org is None too."""
    query = db.query(Organization).filter_by(prefix=prefix)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.first()


def name_for_guild(db, guild_id: object) -> str | None:
    """The name of the active org on this Discord server, or None."""
    org = db.query(Organization).filter_by(guild_id=str(guild_id), is_active=True).first()
    return cast(str, org.name) if org else None


def module_enabled(org: Organization, name: str) -> bool:
    if name not in OPTIONAL_MODULES:
        return True
    settings = (org.config or {}).get("modules") or {}
    return settings.get(name, True) is not False


def module_states(org: Organization) -> list[dict]:
    return [
        {"name": name, "description": description, "enabled": module_enabled(org, name)}
        for name, description in OPTIONAL_MODULES.items()
    ]


def set_modules(db, org: Organization, changes: object) -> list[dict]:
    """Turn modules on or off. `changes` maps module name to a bool. Commits."""
    if not isinstance(changes, dict) or not changes:
        raise ModuleError("Send a non-empty object of module name to true or false")
    for name, enabled in changes.items():
        if name not in OPTIONAL_MODULES:
            raise ModuleError(f"Unknown or required module: {name}")
        if not isinstance(enabled, bool):
            raise ModuleError(f"Value for {name} must be true or false")
    config = dict(cast(dict, org.config) or {})
    config["modules"] = {**(config.get("modules") or {}), **changes}
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return module_states(org)


def create_organization(
    db,
    *,
    name: str,
    prefix: str,
    guild_id: str,
    officer_role_id: str | None = None,
    description: str | None = None,
    modules_off: tuple[str, ...] = (),
) -> Organization:
    """Create an org with default settings and the given optional modules turned off. Commits."""
    from modules.organizations.config import OrganizationSettings

    if not PREFIX_PATTERN.match(prefix):
        raise OrganizationError("Prefix must be 2-20 characters of lowercase letters, numbers, - and _")
    if not str(guild_id).isdigit():
        raise OrganizationError("Guild id must be a Discord id (digits only)")
    if find_by_prefix(db, prefix):
        raise OrganizationError(f"Prefix {prefix} is taken")
    if db.query(Organization).filter_by(guild_id=str(guild_id)).first():
        raise OrganizationError(f"Guild {guild_id} already has an organization")
    unknown = [m for m in modules_off if m not in OPTIONAL_MODULES]
    if unknown:
        raise OrganizationError(f"Unknown or required module: {', '.join(unknown)}")
    config = OrganizationSettings().to_dict()
    if modules_off:
        config["modules"] = dict.fromkeys(modules_off, False)
    org = Organization(
        name=name,
        prefix=prefix,
        guild_id=str(guild_id),
        officer_role_id=officer_role_id,
        description=description,
        is_active=True,
        config=config,
    )
    db.add(org)
    db.commit()
    return org


def branding(org: Organization) -> dict:
    """The org's logo URL, accent color and website URL from config.branding, each None when unset."""
    saved = (cast(dict, org.config) or {}).get("branding") or {}
    return {key: saved.get(key) or None for key in BRANDING_KEYS}


def _clean_url(field: str, value: object) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > MAX_URL:
        raise BrandingError(f"{field} must be an https URL of at most {MAX_URL} characters")
    if any(ch.isspace() or ord(ch) < 32 for ch in value):
        raise BrandingError(f"{field} must not contain spaces or control characters")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise BrandingError(f"{field} must be an https URL")
    return value


def _clean_accent(value: object) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not ACCENT_PATTERN.fullmatch(value):
        raise BrandingError("accent_color must be a hex color like #1f6feb")
    return value.lower()


def set_branding(db, org: Organization, changes: object) -> dict:
    """Update the given branding keys. An empty string or null clears a key. Commits."""
    if not isinstance(changes, dict) or not changes:
        raise BrandingError("Send an object with one or more of logo_url, accent_color and website_url")
    unknown = [key for key in changes if key not in BRANDING_KEYS]
    if unknown:
        raise BrandingError(f"Unknown branding field: {', '.join(sorted(unknown))}")
    current = branding(org)
    for field in ("logo_url", "website_url"):
        if field in changes:
            current[field] = _clean_url(field, cast(dict, changes)[field])
    if "accent_color" in changes:
        current["accent_color"] = _clean_accent(cast(dict, changes)["accent_color"])
    config = dict(cast(dict, org.config) or {})
    config["branding"] = {key: value for key, value in current.items() if value}
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return branding(org)


# Org secrets and machine tokens


def active_org(db, org_id: int) -> Organization | None:
    """The active org with this id, or None."""
    return db.query(Organization).filter_by(id=org_id, is_active=True).first()


def secret_names(db, org_id: int) -> dict:
    """Whether SECRETS_KEY is set, and the names of the secrets the org saved. Values are never returned."""
    return {"configured": secrets.configured(), "secrets": secrets.list_secrets(db, org_id)}


def save_secret(db, org_id: int, name: str, value: object, set_by: str | None) -> None:
    """Save an org secret. Raises secrets.SecretsError when the name or value is refused."""
    secrets.set_secret(db, org_id, name, value, set_by)


def delete_secret(db, org_id: int, name: str) -> bool:
    """Delete an org secret. False when it was not set."""
    return secrets.delete_secret(db, org_id, name)


def token_list(db, org_id: int) -> dict:
    """The org's active machine tokens, the scopes a token can hold, and the integrations whose tools a scope gives."""
    from core.integrations import registry

    groups: dict[str, list[str]] = {}
    for scope, integration in scopes.INTEGRATION_SCOPES.items():
        groups.setdefault(integration, []).append(scope)
    integrations = [
        {
            "key": key,
            "title": registry.INTEGRATIONS[key].title if key in registry.INTEGRATIONS else key,
            "connected": registry.connected(db, org_id, key),
            "scopes": sorted(names),
            "limits": sorted(machine_tokens.LIMIT_NAMES.get(key, ())),
        }
        for key, names in sorted(groups.items())
    ]
    return {"tokens": machine_tokens.list_active(db, org_id), "scopes": scopes.SCOPES, "integrations": integrations}


def issue_token(db, org_id: int, data: dict, created_by: str | None) -> dict:
    """Issue a machine token from {"name", "kind", "scopes", "expires_days", "limits"}. The value is in the result only.

    Raises machine_tokens.TokenError when the request is refused.
    """
    value, row = machine_tokens.issue(
        db,
        organization_id=org_id,
        name=data.get("name"),
        kind=data.get("kind"),
        scopes=data.get("scopes"),
        created_by=created_by,
        expires_days=data.get("expires_days"),
        limits=data.get("limits"),
    )
    return {"token": value, **machine_tokens.to_dict(row)}


def revoke_token(db, org_id: int, token_id: int) -> bool:
    """Revoke a machine token of the org. False when there is none."""
    return machine_tokens.revoke(db, org_id, token_id)
