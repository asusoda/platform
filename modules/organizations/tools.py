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


@tool(
    "org.set_modules",
    description='Turn optional modules on or off, for example {"points": false}.',
    scope="settings:write",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"modules": {"type": "object", "additionalProperties": {"type": "boolean"}, "minProperties": 1}},
        "required": ["modules"],
        "additionalProperties": False,
    },
)
def org_set_modules(db, org, caller, modules: dict):
    return {"modules": service.set_modules(db, org, modules)}


@tool("org.branding", description="The org's logo, accent color and website.", scope="org:read")
def org_branding(db, org, caller):
    return service.branding(org)


@tool(
    "org.set_branding",
    description="Change the org's branding. Send only the fields to change; null clears a field.",
    scope="settings:write",
    input_schema={
        "type": "object",
        "properties": {
            "logo_url": {"type": ["string", "null"], "maxLength": 500},
            "accent_color": {"type": ["string", "null"], "maxLength": 7},
            "website_url": {"type": ["string", "null"], "maxLength": 500},
        },
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def org_set_branding(db, org, caller, **changes):
    return service.set_branding(db, org, changes)
