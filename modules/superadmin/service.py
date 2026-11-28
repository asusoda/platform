"""Superadmin logic: guilds without an org, an officer's orgs, guild roles, new orgs, the org list, the server's
health and services, and each org's limits. No Flask here."""

import re
from typing import Any

from sqlalchemy import Table, delete, func, or_, select, update

from core import error_log, host, hosting, jobs
from core import limits as core_limits
from core.audit import AuditEntry
from core.config import superadmin_ids
from core.db import Base
from core.error_log import ErrorGroup
from core.errors import ServiceError
from core.hosting import server as runner
from core.integrations.discord import DiscordUnavailable
from core.log import get_logger
from core.time import utcnow
from hosting.models import App
from modules.godfather.models import ComputePod
from modules.members.models import UserOrganizationMembership
from modules.organizations import service as organizations
from modules.organizations.models import Organization
from modules.superadmin.models import ServiceOwner

logger = get_logger(__name__)


def is_superadmin(discord_id: object) -> bool:
    """Whether the Discord id is one of the ids in SYS_ADMIN."""
    return str(discord_id) in superadmin_ids()


ORG_HAS_PODS = "The org has apps or pods on a hosting provider. Delete them first, then delete the org"


def _org_filters(table: Table, owned: dict[str, Any], org_id: int) -> list[Any]:
    """The conditions that select the rows of table that belong to the org, directly or through a parent row."""
    filters = []
    for fk in table.foreign_keys:
        parent = fk.column.table
        if parent.name == "organizations":
            if fk.ondelete != "SET NULL":
                filters.append(fk.parent == org_id)
        elif parent.name in owned:
            ids = select(fk.column).where(owned[parent.name])
            filters.append(fk.parent.in_(ids))
    return filters


def delete_organization(db, org_id: int) -> str:
    """Delete the org and every row that belongs to it. Returns the org's name. Commits.

    Rows that refer to the org with ON DELETE SET NULL, such as submodules, stay and lose the org.
    Refuses with 409 while an app of the org has a pod, or the org has a godfather pod.
    """
    org = db.get(Organization, org_id)
    if org is None:
        raise ServiceError("Organization not found", 404)
    pods = db.query(ComputePod.id).filter_by(organization_id=org_id).first()
    apps = db.query(App.id).filter(App.organization_id == org_id, App.pod_id.is_not(None)).first()
    if pods is not None or apps is not None:
        raise ServiceError(ORG_HAS_PODS, 409)
    name = str(org.name)
    tables = Base.metadata.sorted_tables
    owned: dict[str, Any] = {}
    for table in tables:
        filters = _org_filters(table, owned, org_id)
        if filters:
            owned[table.name] = or_(*filters)
    for table in reversed(tables):
        for fk in table.foreign_keys:
            if fk.column.table.name == "organizations" and fk.ondelete == "SET NULL":
                db.execute(update(table).where(fk.parent == org_id).values({fk.parent.name: None}))
        if table.name in owned:
            db.execute(delete(table).where(owned[table.name]))
    db.expunge(org)
    db.execute(delete(Organization.__table__).where(Organization.__table__.c.id == org_id))
    db.commit()
    logger.info("org deleted id=%s name=%s", org_id, name)
    return name


def available_guilds(guilds: list[dict], orgs: list[Organization]) -> list[dict]:
    """The bot's guilds that have no org yet."""
    taken = {org.guild_id for org in orgs}
    return [
        {"id": guild["id"], "name": guild["name"], "icon": {"url": guild["icon_url"]}}
        for guild in guilds
        if guild["id"] not in taken
    ]


def officer_orgs(directory, orgs: list[Organization], officer_id: object) -> list[Organization]:
    """The orgs whose guild has the member. An org whose guild cannot be read is left out."""
    if not officer_id:
        return []
    found = []
    for org in orgs:
        try:
            if directory.check_user_membership(officer_id, org.guild_id):
                found.append(org)
        except (ValueError, DiscordUnavailable) as e:
            logger.debug("officer org check skipped org_id=%s guild_id=%s: %s", org.id, org.guild_id, e)
    return found


def guild_roles(directory, guild_id: int) -> list[dict]:
    """The guild's roles without @everyone and integration roles, highest position first."""
    roles = [
        {key: role[key] for key in ("id", "name", "color", "position", "permissions")}
        for role in directory.get_guild_roles(guild_id)
        if role["name"] != "@everyone" and not role["managed"]
    ]
    roles.sort(key=lambda x: x["position"], reverse=True)
    return roles


def role_in_guild(directory, guild_id: Any, role_id: Any) -> bool:
    """Whether the guild has the role. Raises ValueError when an id is not a number."""
    role_ids = {role["id"] for role in directory.get_guild_roles(int(guild_id))}
    return str(int(role_id)) in role_ids


def find_org(db, org_id: int) -> Organization:
    org = db.query(Organization).filter_by(id=org_id).first()
    if org is None:
        raise ServiceError("Organization not found", 404)
    return org


def ready_directory(directory):
    """The Discord directory when the bot is ready. Raises ServiceError 503 when it is not."""
    if directory is None or not directory.is_ready():
        raise ServiceError("Bot not available", 503)
    return directory


def find_guild(directory, guild_id: object) -> dict:
    """A guild that the bot is in. Raises ServiceError: 503 with no bot, 400 for a bad id, 404 for no guild."""
    ready_directory(directory)
    try:
        number = int(str(guild_id))
    except ValueError as e:
        logger.warning("superadmin guild refused: guild_id=%r is not a number", guild_id)
        raise ServiceError("Invalid guild ID format", 400) from e
    guild = directory.get_guild(number)
    if not guild:
        logger.warning("superadmin guild refused: the bot is not in guild_id=%s", number)
        raise ServiceError("Guild not found", 404)
    return guild


def dashboard(db, directory, officer_id: object) -> dict:
    """Guilds without an org, every org, and the orgs whose guild has the officer. Raises ServiceError 503."""
    ready_directory(directory)
    guilds = directory.list_guilds()
    orgs = db.query(Organization).all()
    return {
        "available_guilds": available_guilds(guilds, orgs),
        "existing_orgs": [org.to_dict() for org in orgs],
        "officer_orgs": [org.to_dict() for org in officer_orgs(directory, orgs, officer_id)],
    }


def roles_of_guild(directory, guild_id: object) -> list[dict]:
    """The roles of a guild that the bot is in, as guild_roles gives them. Raises ServiceError."""
    find_guild(directory, guild_id)
    return guild_roles(directory, int(str(guild_id)))


def set_officer_role(db, directory, org_id: int, data: Any) -> dict:
    """Set the org's officer role, after a check that its guild has the role. An empty id clears it. Commits."""
    if not data or "officer_role_id" not in data:
        raise ServiceError("officer_role_id is required", 400)
    officer_role_id = data["officer_role_id"]
    ready_directory(directory)
    org = find_org(db, org_id)
    try:
        if not directory.get_guild(int(org.guild_id)):
            logger.warning("officer role refused: the bot is not in guild_id=%s org_id=%s", org.guild_id, org_id)
            raise ServiceError("Guild not found", 404)
        if officer_role_id and not role_in_guild(directory, org.guild_id, officer_role_id):
            logger.warning("officer role refused: role_id=%s is not in guild_id=%s", officer_role_id, org.guild_id)
            raise ServiceError("Role not found in guild", 404)
    except (ValueError, AttributeError) as e:
        logger.warning("officer role refused: role_id=%r org_id=%s: %s", officer_role_id, org_id, e)
        raise ServiceError("Invalid role ID format", 400) from e
    org.officer_role_id = officer_role_id
    db.commit()
    logger.info("officer role set org_id=%s role_id=%s", org_id, officer_role_id)
    return {"message": f"Officer role updated successfully for {org.name}", "organization": org.to_dict()}


ERROR_ACTIONS = ("resolve", "reopen")
MAX_ERROR_IDS = 200


def change_errors(db, action: str, ids: Any) -> dict:
    """Resolve or reopen error groups of any org. Raises ServiceError: 404 for another action, 400 for bad ids."""
    if action not in ERROR_ACTIONS:
        raise ServiceError("Unknown action", 404)
    if not isinstance(ids, list) or not ids or len(ids) > MAX_ERROR_IDS or not all(isinstance(i, int) for i in ids):
        raise ServiceError(f"ids must be a list of 1 to {MAX_ERROR_IDS} error ids", 400)
    return {"changed": error_log.set_resolved(db, ids, resolved=action == "resolve", actor="superadmin")}


def prefix_for(name: str, guild_id: object) -> str:
    """A prefix from a guild name: lowercase letters, digits and underscores, 2 to 20 characters."""
    prefix = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:20].rstrip("_")
    if len(prefix) < 2:
        return f"org_{str(guild_id)[-6:]}"
    return f"{prefix[:16]}_org" if prefix in organizations.RESERVED_PREFIXES else prefix


def add_organization(db, guild: dict) -> Organization:
    """Create the org for a guild through organizations.create_organization, with a prefix from the guild name.

    Raises ServiceError: 409 when the prefix is taken or the guild has an org, 400 for any other refusal. Commits.
    """
    prefix = prefix_for(guild["name"], guild["id"])
    if organizations.find_by_prefix(db, prefix) is not None:
        raise ServiceError(f"The prefix {prefix} is already taken", 409)
    if db.query(Organization.id).filter_by(guild_id=str(guild["id"])).first() is not None:
        raise ServiceError(f"Guild {guild['id']} already has an organization", 409)
    try:
        org = organizations.create_organization(
            db,
            name=guild["name"],
            prefix=prefix,
            guild_id=str(guild["id"]),
            description=f"Discord server: {guild['name']}",
        )
    except organizations.OrganizationError as e:
        db.rollback()
        raise ServiceError(str(e), 400) from e
    org.icon_url = guild.get("icon_url")
    db.commit()
    logger.info("org added id=%s prefix=%s guild=%s", org.id, org.prefix, org.guild_id)
    return org


# A limit is near when the org uses this share of it or more
NEAR = 0.8


def org_list(db) -> list[dict]:
    """Every org with its member count, modules on, limits near, open errors and last audit time. Needs no bot."""
    orgs = db.query(Organization).order_by(Organization.name).all()
    members = dict(
        db.query(UserOrganizationMembership.organization_id, func.count(UserOrganizationMembership.id))
        .group_by(UserOrganizationMembership.organization_id)
        .all()
    )
    errors = dict(
        db.query(ErrorGroup.org, func.count(ErrorGroup.id))
        .filter(ErrorGroup.resolved_at.is_(None), ErrorGroup.org.isnot(None))
        .group_by(ErrorGroup.org)
        .all()
    )
    audited = dict(
        db.query(AuditEntry.org, func.max(AuditEntry.created_at))
        .filter(AuditEntry.org.isnot(None))
        .group_by(AuditEntry.org)
        .all()
    )
    rows = []
    for org in orgs:
        last = audited.get(org.prefix)
        rows.append(
            {
                "id": org.id,
                "name": org.name,
                "prefix": org.prefix,
                "guild_id": org.guild_id,
                "icon_url": org.icon_url,
                "is_active": org.is_active,
                "officer_role_id": org.officer_role_id,
                "created_at": org.created_at.isoformat() if org.created_at else None,
                "members": members.get(org.id, 0),
                "modules_on": [m["name"] for m in organizations.module_states(org) if m["enabled"]],
                "near": org_limits(db, org)["near"],
                "open_errors": errors.get(org.prefix, 0),
                "last_activity": last.isoformat() if last else None,
            }
        )
    return rows


def server(db, bot_ready: bool | None) -> dict:
    """The server's health, whether the Discord bot answers, and the job queue."""
    return host.stats(db) | {
        "bot_ready": bot_ready,
        "jobs": {"backend": jobs.queue_backend(), "queue": jobs.queue_counts(db)},
    }


def _near(row: dict) -> bool:
    return row["value"] is not None and row["enabled"] and row["used"] >= NEAR * max(row["value"], 1)


def org_limits(db, org: Organization) -> dict:
    """The org, its limits with what it uses, and its overrides."""
    rows = organizations.limits(db, org)
    return {
        "org": {"id": org.id, "name": org.name, "prefix": org.prefix, "is_active": org.is_active},
        "limits": rows,
        "near": sorted(row["key"] for row in rows if _near(row)),
        "overrides": core_limits.overrides_of(db, org.id),
    }


def all_limits(db) -> dict:
    """Every declared limit, and each org's limits and use."""
    orgs = db.query(Organization).order_by(Organization.name).all()
    return {
        "catalog": core_limits.catalog(),
        "near": NEAR,
        "orgs": [org_limits(db, org) for org in orgs],
    }


def set_org_limits(db, org: Organization, changes: object, actor: str | None) -> dict:
    """Set the org's overrides. Commits."""
    core_limits.set_values(db, org.id, changes, actor=actor)
    return org_limits(db, org)


OWNERS = ("platform", "infrastructure", "org")
MAX_SERVICE_NAME = 128


class ServerError(ServiceError):
    """A bad request about the server's services."""


def _owner_of(service: dict, row: ServiceOwner | None, orgs: dict) -> dict:
    """The owner the superadmin set; else the org of a platform.org label; else Platform for Platform's own
    containers."""
    if row is not None:
        org = orgs["id"].get(row.organization_id)
        return {"owner": row.owner, "org": org, "set": True}
    if service.get("org") and service["org"] in orgs["prefix"]:
        return {"owner": "org", "org": orgs["prefix"][service["org"]], "set": False}
    if service.get("platform"):
        return {"owner": "platform", "org": None, "set": False}
    return {"owner": None, "org": None, "set": False}


def server_services(db) -> dict:
    """Each container and host process on the server, from the host agent, with its owner."""
    snapshot = host.agent_snapshot()
    if snapshot is None:
        return {"agent": None, "services": []}
    rows = {row.name: row for row in db.query(ServiceOwner).all()}
    orgs: dict[str, dict] = {"id": {}, "prefix": {}}
    for org in db.query(Organization).all():
        brief = {"id": org.id, "name": org.name, "prefix": org.prefix}
        orgs["id"][org.id] = brief
        orgs["prefix"][org.prefix] = brief
    services = [
        {
            key: s.get(key)
            for key in (
                "name",
                "kind",
                "state",
                "status",
                "image",
                "project",
                "memory_used",
                "memory_limit",
                "cpu_percent",
                "ports",
                "domains",
            )
        }
        | _owner_of(s, rows.get(s.get("name")), orgs)
        for s in snapshot["services"]
        if isinstance(s, dict) and s.get("name")
    ]
    return {"agent": {"age_seconds": snapshot["age_seconds"], "stale": snapshot["stale"]}, "services": services}


def set_service_owner(db, name: str, body: Any, actor: str | None) -> dict:
    """Set the owner of a service: {"owner": "platform" | "infrastructure" | "org" | null, "organization_id": id}.
    null goes back to the owner from the labels. Commits."""
    if not name or len(name) > MAX_SERVICE_NAME:
        raise ServerError(f"The service name must have 1 to {MAX_SERVICE_NAME} characters")
    if not isinstance(body, dict) or "owner" not in body:
        raise ServerError('Send "owner": platform, infrastructure, org or null')
    owner, org_id = body.get("owner"), body.get("organization_id")
    row = db.query(ServiceOwner).filter_by(name=name).first()
    if owner is None:
        if row is not None:
            db.delete(row)
            db.commit()
        logger.info("service owner cleared name=%s actor=%s", name, actor)
        return {"name": name, "owner": None}
    if owner not in OWNERS:
        raise ServerError(f"owner must be one of {', '.join(OWNERS)}, or null")
    if owner == "org":
        if not isinstance(org_id, int) or isinstance(org_id, bool) or db.get(Organization, org_id) is None:
            raise ServerError("organization_id must be the id of an org")
    else:
        org_id = None
    if row is None:
        row = ServiceOwner(name=name)
        db.add(row)
    row.owner, row.organization_id, row.updated_at, row.updated_by = owner, org_id, utcnow(), actor
    db.commit()
    logger.info("service owner set name=%s owner=%s org=%s actor=%s", name, owner, org_id, actor)
    return {"name": name, "owner": owner, "organization_id": org_id}


SERVICE_ACTIONS = ("start", "stop", "restart")


def _target(name: str) -> tuple[str, str | None, str]:
    """How to control a service of the host agent's list: ("app", org or None, container), ("containers", None,
    name) or ("units", None, unit). Raises ServerError when the service cannot be controlled."""
    snapshot = host.agent_snapshot()
    found = next((s for s in (snapshot or {}).get("services", []) if s.get("name") == name), None)
    if found is None:
        raise ServerError("No service with this name on the server", 404)
    if found.get("kind") == "container":
        if name.startswith(("app-", "shared-")):
            for app in runner.call("GET", "/apps")["apps"]:
                if app.get("id") == name:
                    return "app", (None if app.get("shared") else str(app["org"])), name
        return "containers", None, name
    if str(found.get("status") or "").startswith("systemd "):
        return "units", None, name
    raise ServerError("This process is not in a systemd unit, so it cannot be controlled", 409)


def service_action(db, name: str, action: object, actor: str | None) -> dict:
    """Start, stop or restart a service: an app container through its app, another container or unit through the
    runner's host_control list."""
    if action not in SERVICE_ACTIONS:
        raise ServerError(f"action must be one of {', '.join(SERVICE_ACTIONS)}")
    try:
        kind, org, target = _target(name)
        if kind == "app":
            client = runner.ServerClient(org)
            {"start": client.start_pod, "stop": client.stop_pod, "restart": client.restart_pod}[str(action)](target)
            result = {"name": name, "state": str((client.get_pod(target) or {}).get("state"))}
        else:
            result = runner.host_action(kind, target, str(action))
    except hosting.HostingError as e:
        raise ServerError(e.message, e.status or 502) from e
    logger.info("service %s name=%s actor=%s", action, name, actor)
    return result


def service_logs(db, name: str, lines: int = 200) -> dict:
    """The last lines of a service's output."""
    try:
        kind, org, target = _target(name)
        if kind == "app":
            return {"logs": runner.ServerClient(org).logs(target, lines)}
        return {"logs": runner.host_logs(kind, target, lines)}
    except hosting.HostingError as e:
        raise ServerError(e.message, e.status or 502) from e
