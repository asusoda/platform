"""Lists and runs tools for a machine token. Shared by the MCP server and /api/tools. No Flask here.

The tools are the modules' tools in core.tools.TOOLS and the tools of connected services that
modules/integrations passes through to their MCP servers.
"""

import time
from typing import Any

import jsonschema

from core import audit
from core.errors import ServiceError
from core.log import get_logger
from core.tools import TOOLS, ToolError, ToolSpec
from modules.auth.machine_tokens import MachineCaller
from modules.integrations import service as remote
from modules.organizations import service as organizations
from modules.organizations.models import Organization

logger = get_logger("tools")


def _org(db, caller: MachineCaller) -> Organization:
    org = db.query(Organization).filter_by(id=caller.organization_id, is_active=True).first()
    if org is None:
        raise ToolError("The token's organization is inactive or gone", 403)
    return org


def _usable(spec: ToolSpec, org: Organization, caller: MachineCaller) -> bool:
    if not caller.allows(spec.scope):
        return False
    return spec.module is None or organizations.module_enabled(org, spec.module)


def available(db, caller: MachineCaller) -> list[ToolSpec]:
    """Tools this token may call: its scopes allow them and its org has their module on."""
    org = _org(db, caller)
    local = [spec for spec in TOOLS.values() if _usable(spec, org, caller)]
    return sorted(local + remote.tools_for(db, caller.organization_id, caller), key=lambda s: s.name)


def call(db, caller: MachineCaller, name: str, arguments: dict | None, *, source: str) -> Any:
    """Run one tool. Raises ToolError. Every call, refused or not, is written to the audit log."""
    started = time.monotonic()
    status = 200
    pending = False
    try:
        org = _org(db, caller)
        spec = TOOLS.get(name)
        if spec is not None and not _usable(spec, org, caller):
            spec = None
        if spec is None and name not in TOOLS:
            spec = remote.find(db, caller.organization_id, caller, name)
        if spec is None:
            # Same answer for unknown and not allowed, so a token cannot probe for tools
            raise ToolError(f"No tool named {name}", 404)
        args = dict(arguments or {})
        try:
            jsonschema.validate(args, spec.input_schema)
        except jsonschema.ValidationError as e:
            raise ToolError(f"Invalid arguments: {e.message}", 400) from e
        confirmed = args.pop("confirm", False) is True
        if spec.confirm and not confirmed:
            pending = True
            result = _preview(spec, args)
            if spec.preview is not None:
                result["preview"] = spec.preview(db, org, caller, **args)
            return result
        return spec.func(db, org, caller, **args)
    except ToolError as e:
        status = e.status
        raise
    except ServiceError as e:
        status = e.status
        raise ToolError(e.message, e.status) from e
    except Exception:
        status = 500
        logger.exception("tool failed name=%s", name)
        raise ToolError("Tool failed", 500) from None
    finally:
        audit.record(
            f"tool {name}",
            source=source,
            org=None if status == 403 else _prefix(db, caller),
            actor_kind="machine",
            actor_id=caller.actor,
            status=status,
            details={"ms": round((time.monotonic() - started) * 1000)} | ({"confirm": "pending"} if pending else {}),
        )


def _preview(spec: ToolSpec, args: dict) -> dict:
    """The answer to a confirm tool called without confirm=true. Nothing has changed."""
    return {
        "confirm_required": True,
        "tool": spec.name,
        "arguments": args,
        "message": f"Nothing changed. To run {spec.name}, call it again with the same arguments and confirm=true.",
    }


def _prefix(db, caller: MachineCaller) -> str | None:
    org = db.query(Organization).filter_by(id=caller.organization_id).first()
    return str(org.prefix) if org else None


def describe(spec: ToolSpec) -> dict:
    return {
        "name": spec.name,
        "description": spec.description,
        "scope": spec.scope,
        "read_only": spec.read_only,
        "confirm": spec.confirm,
        "input_schema": spec.input_schema,
    }
