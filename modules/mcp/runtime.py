"""Lists and runs tools for a machine token. Shared by the MCP server and /api/tools. No Flask here."""

import time
from typing import Any

import jsonschema

from core import audit
from core.errors import ServiceError
from core.log import get_logger
from core.tools import TOOLS, ToolError, ToolSpec
from modules.auth.machine_tokens import MachineCaller
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
    return [spec for spec in sorted(TOOLS.values(), key=lambda s: s.name) if _usable(spec, org, caller)]


def call(db, caller: MachineCaller, name: str, arguments: dict | None, *, source: str) -> Any:
    """Run one tool. Raises ToolError. Every call, refused or not, is written to the audit log."""
    started = time.monotonic()
    status = 200
    try:
        spec = TOOLS.get(name)
        org = _org(db, caller)
        if spec is None or not _usable(spec, org, caller):
            # Same answer for unknown and not allowed, so a token cannot probe for tools
            raise ToolError(f"No tool named {name}", 404)
        args = arguments or {}
        try:
            jsonschema.validate(args, spec.input_schema)
        except jsonschema.ValidationError as e:
            raise ToolError(f"Invalid arguments: {e.message}", 400) from e
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
            actor_id=f"{caller.kind}:{caller.name}#{caller.token_id}",
            status=status,
            details={"ms": round((time.monotonic() - started) * 1000)},
        )


def _prefix(db, caller: MachineCaller) -> str | None:
    org = db.query(Organization).filter_by(id=caller.organization_id).first()
    return str(org.prefix) if org else None


def describe(spec: ToolSpec) -> dict:
    return {"name": spec.name, "description": spec.description, "scope": spec.scope, "input_schema": spec.input_schema}
