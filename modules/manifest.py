"""Module categories, the module catalog, sub-modules, layers, and the modules that hold models, jobs and tools.

Flask-free, so alembic, the worker and MCP can load it.
"""

import importlib
from dataclasses import dataclass
from pathlib import Path

from core import submodules

ROOT = Path(__file__).resolve().parent.parent

# Each module and its category, in the order of the Explore page and the sidebar of the dashboard. A category
# names modules, or sub-modules by their key when the parent is Core (bot). Core modules are always on and do not
# show on Explore.
CATEGORIES = {
    "Core": [
        "alerts",
        "auth",
        "bot",
        "dashboard",
        "mcp",
        "members",
        "organizations",
        "public",
        "submodules",
        "superadmin",
    ],
    "Members": ["points"],
    "AI": ["knowledge", "integrations"],
    "Automations": ["feeds", "calendar", "uptime"],
    "Discord": ["bot.leetcode", "bot.games"],
    "Compute": ["godfather"],
}

# The sub-modules of each module: the folders in modules/<module>/submodules/. Each sets SUBMODULE in its
# __init__.py, and its switch key is <module>.<name>.
SUBMODULES = {
    "bot": ("leetcode", "games"),
    "points": ("leaderboard", "checkins", "store"),
}

CORE = "Core"


@dataclass(frozen=True)
class Need:
    """An integration or a setting that a module needs."""

    # The key of an integration in core.integrations.registry, or the name of a setting in .env
    key: str
    # The name the dashboard shows, such as "Google service account"
    label: str
    # integration or setting
    kind: str = "integration"
    # The module works without it, with fewer functions
    optional: bool = False


@dataclass(frozen=True)
class ModuleInfo:
    """How the Explore page of the dashboard shows a module."""

    title: str
    description: str
    needs: tuple[Need, ...] = ()
    # The shared content in submodules/ that the module reads
    shared_content: tuple[str, ...] = ()


DISCORD_BOT = Need("discord", "Discord bot")
RUNPOD = Need("runpod", "RunPod")

# Each module as the dashboard shows it. tests/test_module_layout.py checks that each module has an entry.
CATALOG = {
    "auth": ModuleInfo(
        "Sign-in", "Discord sign-in for officers and members, tokens and access checks.", (DISCORD_BOT,)
    ),
    "bot": ModuleInfo("Discord bot", "The Discord bot that runs the commands of other modules.", (DISCORD_BOT,)),
    "calendar": ModuleInfo(
        "Calendar sync",
        "Copies Notion events to Google Calendar and the public events feed.",
        needs=(Need("notion", "Notion"), Need("google", "Google service account")),
    ),
    "godfather": ModuleInfo("Godfather", "GPU and CPU pods that members connect to with the Godfather CLI.", (RUNPOD,)),
    "dashboard": ModuleInfo("Dashboard", "This dashboard: overview, activity, errors and branding."),
    "alerts": ModuleInfo(
        "Alerts", "Sends events of the org, such as a failed job or a site that is down, to its Discord channels."
    ),
    "feeds": ModuleInfo(
        "Feeds",
        "Posts new internship and new grad roles from GitHub job lists, and upcoming hackathons, to Discord channels.",
        shared_content=("careers",),
    ),
    "integrations": ModuleInfo("Integration tools", "Gives agents the tools of the services that the org connects."),
    "knowledge": ModuleInfo(
        "Knowledge",
        "Pages and documents that agents search, with crawls on a schedule.",
        needs=(
            Need("embeddings", "Embeddings service", optional=True),
            Need("firecrawl", "Firecrawl", optional=True),
        ),
        shared_content=("asu",),
    ),
    "mcp": ModuleInfo("MCP", "The MCP server that gives agents and apps the tools of each module."),
    "organizations": ModuleInfo("Organizations", "The org record, module switches, secrets and machine tokens."),
    "submodules": ModuleInfo(
        "Shared content",
        "Content made once for every org: campus pages and live queries for Knowledge, and job and hackathon sources "
        "for Feeds. The code name is submodules.",
        needs=(Need("searxng", "Web search (SearXNG)", optional=True),),
        shared_content=("asu", "careers"),
    ),
    "points": ModuleInfo("Points", "Points, leaderboards and event check-ins."),
    "public": ModuleInfo("Public pages", "Open routes for the leaderboard, the member list and stats."),
    "superadmin": ModuleInfo("Superadmin", "Orgs for the whole deployment. Only the superadmin uses it."),
    "uptime": ModuleInfo(
        "Uptime", "Checks the org's sites and Hosting apps, with an event when one goes down or comes back."
    ),
    "members": ModuleInfo("Member list", "The members of the org and their profile fields."),
}

# Packages outside modules/ that the dashboard shows like a module, in their own sidebar section. hosting/ is the
# apps layer: the org's own apps, which run on a hosting provider and are not Platform code.
LAYERS = {
    "hosting": ModuleInfo(
        "Hosting",
        "Deploys the org's apps to a hosting provider, and rolls back to an earlier tag.",
        needs=(RUNPOD, Need("github", "GitHub", optional=True)),
    ),
}


def folder(name: str) -> Path:
    """The folder of a module, a sub-module key such as points.store, or a layer such as hosting."""
    if name in LAYERS:
        return ROOT / name
    module, _, sub = name.partition(".")
    return ROOT / "modules" / module / "submodules" / sub if sub else ROOT / "modules" / module


def info(name: str) -> ModuleInfo | None:
    """How the dashboard shows a module, a sub-module or a layer, or None. A sub-module has the needs of its module."""
    sub = submodules.get(name)
    if sub is not None:
        parent = CATALOG.get(sub.module)
        return ModuleInfo(sub.title, sub.description, parent.needs if parent else ())
    return CATALOG.get(name) or LAYERS.get(name)


# The modules that a new org starts with, in addition to Core. Each other module that an org can switch off starts off.
NEW_ORG_MODULES: tuple[str, ...] = ()


# Importing these puts every table in Base.metadata (alembic/env.py, tests/conftest.py)
MODEL_MODULES = [
    "core.audit",
    "core.error_log",
    "core.limits",
    "core.secrets",
    "core.webhooks",
    "modules.alerts.models",
    "modules.feeds.models",
    "modules.auth.models",
    "modules.bot.submodules.games.models",
    "modules.bot.submodules.leetcode.models",
    "modules.knowledge.models",
    "modules.mcp.models",
    "modules.calendar.models",
    "modules.godfather.models",
    "modules.organizations.models",
    "modules.points.models",
    "hosting.models",
    "modules.points.submodules.store.models",
    "modules.submodules.models",
    "modules.superadmin.models",
    "modules.uptime.models",
    "modules.members.models",
]

# Importing a jobs module registers its jobs with core.jobs
JOB_MODULES = [
    "core.audit",
    "core.error_log",
    "core.limits",
    "core.webhooks",
    "modules.alerts.jobs",
    "modules.auth.jobs",
    "modules.points.submodules.checkins.jobs",
    "modules.calendar.jobs",
    "hosting.jobs",
    "modules.knowledge.jobs",
    "modules.submodules.jobs",
    "modules.bot.submodules.leetcode.jobs",
    "modules.godfather.jobs",
    "modules.feeds.jobs",
    "modules.uptime.jobs",
    "modules.mcp.jobs",
]

# Importing a tools module registers its tools with core.tools
TOOL_MODULES = [
    "modules.organizations.tools",
    "modules.calendar.tools",
    "modules.points.tools",
    "modules.points.submodules.checkins.tools",
    "modules.points.submodules.leaderboard.tools",
    "modules.knowledge.tools",
    "hosting.tools",
    "modules.submodules.tools",
    "modules.dashboard.tools",
    "modules.alerts.tools",
    "modules.feeds.tools",
    "modules.godfather.tools",
    "modules.integrations.tools",
    "modules.uptime.tools",
    "modules.members.tools",
    "modules.bot.tools",
    "modules.points.submodules.store.tools",
    "modules.bot.submodules.leetcode.tools",
    "modules.superadmin.tools",
]


def _load(names: list[str]) -> None:
    for name in names:
        importlib.import_module(name)


def submodule_packages() -> list[str]:
    return [f"modules.{module}.submodules.{name}" for module, names in SUBMODULES.items() for name in names]


def load_submodules() -> None:
    """Register the SUBMODULE of each folder in SUBMODULES."""
    submodules.load(submodule_packages())


def load_models() -> None:
    """Every sub-module, then every model."""
    load_submodules()
    _load(MODEL_MODULES)


def load_jobs() -> None:
    """Every model, then every job. A job can query any table."""
    load_models()
    _load(JOB_MODULES)


def load_tools() -> None:
    """Every model, then every tool. A tool can query any table."""
    load_models()
    _load(TOOL_MODULES)
