"""Organization logic shared by the REST API, the bot and jobs. No Flask here."""

import re
from typing import cast

from sqlalchemy.orm.attributes import flag_modified

from modules.auth import scopes
from modules.organizations.models import Organization

scopes.declare("org:read", "Read the org's name, description and enabled modules")

# Modules an organization can turn off. Everything else (auth, users, organizations,
# superadmin, public pages) is always on. A module missing from an org's config is on,
# so existing orgs keep every feature until an officer turns one off.
OPTIONAL_MODULES = {
    "points": "Points, leaderboards and event check-ins",
    "storefront": "Merch store paid with points",
    "calendar": "Notion to Google Calendar sync and the public events feed",
    "leetcode": "Daily LeetCode post in the org's channel, with solve checks",
    "compute": "GPU and CPU pods on the org's RunPod account that members SSH into",
}


class ModuleError(ValueError):
    pass


class OrganizationError(ValueError):
    pass


PREFIX_PATTERN = re.compile(r"^[a-z0-9_-]{2,20}$")


def find_by_prefix(db, org_prefix: str) -> Organization | None:
    return db.query(Organization).filter_by(prefix=org_prefix).first()


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
    if db.query(Organization).filter_by(prefix=prefix).first():
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
