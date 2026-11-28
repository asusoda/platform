"""Tools that apps and agents call over MCP and over HTTP (/api/tools).

A module declares tools in its tools.py with @tool. A tool function receives a database session,
the caller's organization, the caller, and the validated arguments, and returns JSON-ready data.
The runtime that checks tokens, scopes, tool groups and module switches is modules/mcp/runtime.py.

GUARDRAILS has one row for each tool: whether it writes, whether it needs a confirmation, and its rate class.
tool() refuses a name with no row, so no tool ships without one.

- A tool that writes drops the cached org reads after it runs, and MCP clients see it as not read-only.
- A tool with confirm changes or deletes something that is hard to undo. It takes a boolean argument confirm.
  Without confirm=true the runtime does not run it and returns what the call would do.
- A rate class other than normal counts against the org's tools.<class>_per_minute limit, on top of
  mcp.calls_per_minute: live for calls to outside sources, costly for jobs, deploys and pods, send for
  messages that leave Platform.

The group of a tool is the part of its name before the first dot. An org can allow only some groups
(modules/mcp/service.py).

A tool made with integration calls that connected service. The Connections page lists it under the integration.
A tool made with available is shown only to orgs for which available(db, org_id) is true, such as orgs that
saved their own keys for the service.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core import limits
from core.errors import ServiceError


class ToolError(ServiceError):
    """A tool refused or failed. status follows HTTP: 400 bad arguments, 404 not found, and so on."""


# The calls a minute of each rate class for each org; normal has no limit of its own
RATES: dict[str, int | None] = {"normal": None, "live": 30, "costly": 10, "send": 5}
RATE_LABELS = {
    "live": "Tool calls a minute that query an outside source",
    "costly": "Tool calls a minute that start a job, deploy or pod",
    "send": "Tool calls a minute that send a message out of Platform",
}


def rate_limit(rate: str) -> str | None:
    """The limit key of a rate class, or None for normal."""
    return f"tools.{rate}_per_minute" if RATES.get(rate) is not None else None


for _rate, _label in RATE_LABELS.items():
    limits.declare(f"tools.{_rate}_per_minute", "mcp", _label, RATES[_rate], window="minute", unit="calls")


@dataclass(frozen=True)
class Guardrail:
    """The rules of one tool. confirm is only for a tool that writes."""

    writes: bool
    confirm: bool = False
    rate: str = "normal"

    def __post_init__(self) -> None:
        if self.confirm and not self.writes:
            raise ValueError("A guardrail with confirm must write")
        if self.rate not in RATES:
            raise ValueError(f"Unknown rate class {self.rate}")


READ = Guardrail(writes=False)
WRITE = Guardrail(writes=True)
CONFIRM = Guardrail(writes=True, confirm=True)
# A pass-through tool of a connected service: a write needs confirm and counts as costly
REMOTE_READ = READ
REMOTE_WRITE = Guardrail(writes=True, confirm=True, rate="costly")
# batch, guide and the modules gateway: the tools they run have their own rows
GATEWAY = READ

GUARDRAILS: dict[str, Guardrail] = {
    "access.create_token": CONFIRM,
    "access.delete_secret": CONFIRM,
    "access.delete_webhook": CONFIRM,
    "access.revoke_token": CONFIRM,
    "access.save_webhook": WRITE,
    "access.secrets": READ,
    "access.set_secret": CONFIRM,
    "access.test_webhook": Guardrail(writes=True, rate="send"),
    "access.tokens": READ,
    "access.webhooks": READ,
    "activity.ci_runs": READ,
    "activity.delete_error": CONFIRM,
    "activity.delete_notification": CONFIRM,
    "activity.errors": READ,
    "activity.log": READ,
    "activity.notifications": READ,
    "activity.reopen_error": WRITE,
    "activity.reopen_notification": WRITE,
    "activity.resolve_error": WRITE,
    "activity.resolve_notification": WRITE,
    "activity.set_ci_repos": WRITE,
    "calendar.events": READ,
    "calendar.settings": READ,
    "calendar.setup": Guardrail(writes=True, rate="costly"),
    "calendar.sync": Guardrail(writes=True, rate="costly"),
    "calendar.update_settings": WRITE,
    "connections.disconnect": CONFIRM,
    "connections.list": READ,
    "connections.save": CONFIRM,
    "connections.test": Guardrail(writes=False, rate="live"),
    "discord.channels": READ,
    "discord.members": READ,
    "discord.messages": READ,
    "discord.pins": READ,
    "discord.search": READ,
    "discord.server": READ,
    "feeds.delete": CONFIRM,
    "feeds.history": READ,
    "feeds.list": READ,
    "feeds.presets": READ,
    "feeds.run": Guardrail(writes=True, rate="costly"),
    "feeds.save": WRITE,
    "godfather.add_session": CONFIRM,
    "godfather.connected": READ,
    "godfather.create_pod": Guardrail(writes=True, confirm=True, rate="costly"),
    "godfather.delete_file": CONFIRM,
    "godfather.delete_session": WRITE,
    "godfather.list_files": READ,
    "godfather.make_folder": WRITE,
    "godfather.move_file": WRITE,
    "godfather.pod_action": Guardrail(writes=True, confirm=True, rate="costly"),
    "godfather.pod_members": READ,
    "godfather.pods": READ,
    "godfather.read_file": READ,
    "godfather.sessions": READ,
    "godfather.settings": READ,
    "godfather.update_pod": WRITE,
    "godfather.update_settings": WRITE,
    "godfather.write_file": CONFIRM,
    "google.calendar_create_event": CONFIRM,
    "google.calendar_events": READ,
    "google.calendar_list": READ,
    "google.drive_read": READ,
    "google.drive_search": READ,
    "google.gmail_read": READ,
    "google.gmail_search": READ,
    "google.gmail_send": Guardrail(writes=True, confirm=True, rate="send"),
    "google.sheets_append": CONFIRM,
    "google.sheets_read": READ,
    "hosting.action": Guardrail(writes=True, confirm=True, rate="costly"),
    "hosting.create_from_template": Guardrail(writes=True, rate="costly"),
    "hosting.delete": CONFIRM,
    "hosting.deploy": Guardrail(writes=True, confirm=True, rate="costly"),
    "hosting.get": READ,
    "hosting.list": READ,
    "hosting.logs": READ,
    "hosting.mcp_call": WRITE,
    "hosting.mcp_tools": READ,
    "hosting.pod": READ,
    "hosting.providers": READ,
    "hosting.register": WRITE,
    "hosting.rollback": Guardrail(writes=True, confirm=True, rate="costly"),
    "hosting.shared": READ,
    "hosting.subscribe_shared": CONFIRM,
    "hosting.templates": READ,
    "knowledge.add_document": WRITE,
    "knowledge.crawl_now": Guardrail(writes=True, rate="costly"),
    "knowledge.delete_source": CONFIRM,
    "knowledge.embeddings": READ,
    "knowledge.query": READ,
    "knowledge.read_source": READ,
    "knowledge.reembed": Guardrail(writes=True, confirm=True, rate="costly"),
    "knowledge.reindex": Guardrail(writes=True, confirm=True, rate="costly"),
    "knowledge.runs": READ,
    "knowledge.search": READ,
    "knowledge.set_crawl": WRITE,
    "knowledge.settings": READ,
    "knowledge.sources": READ,
    "knowledge.submodules": READ,
    "knowledge.sync_submodule": Guardrail(writes=True, rate="costly"),
    "knowledge.update_settings": WRITE,
    "knowledge.web_search": Guardrail(writes=False, rate="live"),
    "leetcode.settings": READ,
    "leetcode.update_settings": WRITE,
    "members.add": WRITE,
    "members.discord_roles": READ,
    "members.discord_sync": Guardrail(writes=True, confirm=True, rate="costly"),
    "members.list": READ,
    "members.update": WRITE,
    "modules.set": CONFIRM,
    "modules.submodules": READ,
    "modules.subscribe": CONFIRM,
    "modules.unsubscribe": CONFIRM,
    "notion.create_page": CONFIRM,
    "notion.query_database": READ,
    "notion.read_page": READ,
    "notion.search": READ,
    "org.branding": READ,
    "org.info": READ,
    "org.limits": READ,
    "org.overview": READ,
    "org.set_branding": WRITE,
    "org.settings": READ,
    "org.trends": READ,
    "org.update_settings": WRITE,
    "points.award": WRITE,
    "points.delete": CONFIRM,
    "points.entries": READ,
    "points.history": READ,
    "points.import_csv": Guardrail(writes=True, rate="costly"),
    "points.imports": READ,
    "points.leaderboard": READ,
    "search": Guardrail(writes=False, rate="live"),
    "server.commands": READ,
    "server.control": CONFIRM,
    "server.logs": READ,
    "server.run": CONFIRM,
    "server.services": READ,
    "server.shell": CONFIRM,
    "server.status": READ,
    "store.delete_orders": CONFIRM,
    "store.delete_products": CONFIRM,
    "store.orders": READ,
    "store.products": READ,
    "store.save_product": WRITE,
    "store.update_orders": WRITE,
    "uptime.check": WRITE,
    "uptime.delete": CONFIRM,
    "uptime.get": READ,
    "uptime.list": READ,
    "uptime.save": WRITE,
    "uptime.targets": READ,
}


def group(name: str) -> str:
    """The group of a tool: the part of its name before the first dot."""
    return name.split(".", 1)[0]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    scope: str
    func: Callable[..., Any]
    module: str | None = None  # optional module that must be on for the caller's org
    input_schema: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    guard: Guardrail = GATEWAY
    preview: Callable[..., Any] | None = None  # called like func when confirm is missing; it must change nothing
    integration: str | None = None  # the connected service the tool calls
    available: Callable[[Any, int], bool] | None = None  # the org can use the tool now

    @property
    def read_only(self) -> bool:
        return not self.guard.writes

    @property
    def confirm(self) -> bool:
        """The call runs only with confirm=true."""
        return self.guard.confirm

    @property
    def group(self) -> str:
        return group(self.name)


TOOLS: dict[str, ToolSpec] = {}


CONFIRM_NOTE = " Runs only with confirm=true; without it the result says what the call would do."


def with_confirm(schema: dict, description: str) -> tuple[dict, str]:
    """The schema with a boolean confirm argument, and the description with CONFIRM_NOTE."""
    current = schema.get("properties")
    properties: dict[str, Any] = {**current} if isinstance(current, dict) else {}
    properties["confirm"] = {"type": "boolean"}
    return {**schema, "properties": properties}, description + CONFIRM_NOTE


def tool(
    name: str,
    *,
    description: str,
    scope: str,
    module: str | None = None,
    input_schema: dict | None = None,
    preview: Callable[..., Any] | None = None,
    integration: str | None = None,
    available: Callable[[Any, int], bool] | None = None,
):
    """Register a tool with its GUARDRAILS row. The function is called as func(db, org, caller, **arguments)."""
    guard = GUARDRAILS.get(name)
    if guard is None:
        raise ValueError(f"Add {name} to GUARDRAILS in core/tools.py")

    def register(func: Callable[..., Any]) -> Callable[..., Any]:
        schema: dict[str, Any] = input_schema or {"type": "object", "properties": {}}
        text = description
        if guard.confirm:
            schema, text = with_confirm(schema, text)
        TOOLS[name] = ToolSpec(name, text, scope, func, module, schema, guard, preview, integration, available)
        return func

    return register
