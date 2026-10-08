"""Organization tools."""

from core.tools import tool
from modules.organizations import service


@tool(
    "org.info", description="The organization's name, prefix, description and which modules are on.", scope="org:read"
)
def org_info(db, org, caller):
    return {
        "name": org.name,
        "prefix": org.prefix,
        "description": org.description,
        "modules": {m["name"]: m["enabled"] for m in service.module_states(org)},
    }
