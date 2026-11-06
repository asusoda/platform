"""Server tools for the superadmins of the deployment.

A call runs only when the token was made by a superadmin (SYS_ADMIN), whatever its scopes. Containers and units
are those the host agent sees; control, logs and commands go through the This server runner, whose policy lists
what may be touched. There is no free-form shell: server.run runs only a command the policy names.
"""

from core.errors import ServiceError
from core.hosting import HostingError
from core.integrations import server as runner
from core.tools import ToolError, tool
from modules.auth import scopes

from . import service

scopes.declare("server:read", "Read the server's health, services and logs (superadmins only)")
scopes.declare(
    "server:manage", "Start, stop and restart server services and run the runner's named commands (superadmins only)"
)

NAME = {"type": "string", "minLength": 1, "maxLength": service.MAX_SERVICE_NAME}


def _superadmin(caller) -> None:
    if not service.is_superadmin(caller.created_by):
        raise ToolError("Only a token made by a superadmin can use the server tools", 403)


def _run(func):
    try:
        return func()
    except ServiceError as e:
        raise ToolError(e.message, e.status) from e
    except HostingError as e:
        raise ToolError(e.message, e.status or 502) from e


@tool(
    "server.status",
    description="The server's CPU, memory, disk, database size and job queue.",
    scope="server:read",
)
def server_status(db, org, caller):
    _superadmin(caller)
    return service.server(db, None)


@tool(
    "server.services",
    description="Each container and host process the host agent sees: state, image, ports, domains and owner.",
    scope="server:read",
)
def server_services(db, org, caller):
    _superadmin(caller)
    return service.server_services(db)


@tool(
    "server.logs",
    description="The last lines of a service's output. name is a service from server.services.",
    scope="server:read",
    input_schema={
        "type": "object",
        "properties": {"name": NAME, "lines": {"type": "integer", "minimum": 1, "maximum": 1000}},
        "required": ["name"],
        "additionalProperties": False,
    },
)
def server_logs(db, org, caller, name: str, lines: int = 200):
    _superadmin(caller)
    return _run(lambda: service.service_logs(db, name, lines))


@tool(
    "server.control",
    description="Start, stop or restart a service that the runner's policy lists.",
    scope="server:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"name": NAME, "action": {"type": "string", "enum": list(service.SERVICE_ACTIONS)}},
        "required": ["name", "action"],
        "additionalProperties": False,
    },
)
def server_control(db, org, caller, name: str, action: str):
    _superadmin(caller)
    return _run(lambda: service.service_action(db, name, action, caller.actor))


@tool(
    "server.commands",
    description="The named commands that server.run can run, from the runner's policy.",
    scope="server:read",
)
def server_commands(db, org, caller):
    _superadmin(caller)
    return _run(lambda: {"commands": runner.host_commands()})


@tool(
    "server.run",
    description="Run one named command from server.commands, such as health or deploy. Takes no arguments.",
    scope="server:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"name": {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"}},
        "required": ["name"],
        "additionalProperties": False,
    },
)
def server_run(db, org, caller, name: str):
    _superadmin(caller)
    return _run(lambda: runner.host_command(name))
