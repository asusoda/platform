"""Organization logic shared by the REST API, the bot and jobs. No Flask here."""

from typing import cast

from sqlalchemy.orm.attributes import flag_modified

from modules.organizations.models import Organization

# Modules an organization can turn off. Everything else (auth, users, organizations,
# superadmin, public pages) is always on. A module missing from an org's config is on,
# so existing orgs keep every feature until an officer turns one off.
OPTIONAL_MODULES = {
    "points": "Points, leaderboards and event check-ins",
    "storefront": "Merch store paid with points",
    "calendar": "Notion to Google Calendar sync and the public events feed",
}


class ModuleError(ValueError):
    pass


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
