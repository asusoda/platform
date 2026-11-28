"""The tool groups that an org's tokens can reach. No Flask here.

A group is the part of a tool name before the first dot, such as points or github (core.tools.group). layers.py
puts each group in a layer: base, service or module. Organization.config["mcp"]["tool_groups"] holds the allowed
groups. With no list, every group is allowed. A list is closed: a group that a new module adds later is off until
an officer adds it. batch, guide and the modules gateway are always allowed; each tool they run is checked.
"""

from typing import Any, cast

from sqlalchemy.orm.attributes import flag_modified

from core.errors import ServiceError
from core.tools import TOOLS, group
from modules.integrations.servers import SERVERS
from modules.mcp import layers
from modules.organizations.models import Organization

CONFIG_KEY = "mcp"
GROUPS_KEY = "tool_groups"


class ToolGroupError(ServiceError):
    pass


def allowed(org: Organization) -> set[str] | None:
    """The groups the org allows, or None when it allows every group."""
    config = org.config if isinstance(org.config, dict) else {}
    section = config.get(CONFIG_KEY)
    found = section.get(GROUPS_KEY) if isinstance(section, dict) else None
    return {str(g) for g in found} if isinstance(found, list) else None


def reaches(org: Organization, name: str) -> bool:
    """Whether the org's tokens can reach the tool name."""
    groups = allowed(org)
    return groups is None or group(name) in groups


def known() -> dict[str, dict[str, Any]]:
    """Every group: its layer and how many Platform tools it has. A pass-through service has tools None."""
    found: dict[str, dict[str, Any]] = {}
    for spec in sorted(TOOLS.values(), key=lambda s: s.name):
        entry = found.setdefault(spec.group, {"key": spec.group, "layer": layers.layer(spec), "tools": 0})
        entry["tools"] += 1
    for key in SERVERS:
        found.setdefault(key, {"key": key, "layer": "service", "tools": None})
    order = {"base": 0, "service": 1, "module": 2}
    return dict(sorted(found.items(), key=lambda item: (order[item[1]["layer"]], item[0])))


def listing(org: Organization) -> dict:
    """{"allowed": [...] or null, "groups": [{"key", "layer", "tools"}]}."""
    groups = allowed(org)
    return {"allowed": sorted(groups) if groups is not None else None, "groups": list(known().values())}


def set_groups(db, org: Organization, groups: object) -> dict:
    """Set the allowed groups: a list of known group names, or None for every group. Commits."""
    if groups is not None:
        if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
            raise ToolGroupError("groups must be a list of group names or null")
        unknown = sorted(set(groups) - set(known()))
        if unknown:
            raise ToolGroupError(f"Unknown tool groups: {', '.join(unknown)}")
    config = dict(cast(dict, org.config) or {})
    section = dict(config.get(CONFIG_KEY) or {})
    if groups is None:
        section.pop(GROUPS_KEY, None)
    else:
        section[GROUPS_KEY] = sorted(set(cast(list[str], groups)))
    if section:
        config[CONFIG_KEY] = section
    else:
        config.pop(CONFIG_KEY, None)
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return listing(org)
