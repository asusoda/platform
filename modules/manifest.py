"""Module categories, and the modules that hold models, jobs and tools.

Flask-free, so alembic, the worker and MCP can load it.
"""

import importlib
from dataclasses import dataclass

# Each module and its category. modules/ stays flat; the categories group modules in modules/README.md and on the
# Modules page of the dashboard. Core modules are always on and do not show on the Modules page.
CATEGORIES = {
    "Core": ["auth", "bot", "dashboard", "organizations", "public", "superadmin", "users"],
    "Bots": ["games", "leetcode"],
    "AI and agents": ["agents", "integrations", "knowledge", "mcp", "packs"],
    "Members": ["accounts", "points", "storefront"],
    "Automations": ["alerts", "calendar"],
    "Infrastructure": ["compute", "runpod", "uptime"],
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
    """How the Modules page of the dashboard shows a module."""

    title: str
    description: str
    needs: tuple[Need, ...] = ()
    # The packs in packs/ that the module reads
    packs: tuple[str, ...] = ()


DISCORD_BOT = Need("discord", "Discord bot")
RUNPOD = Need("runpod", "RunPod")

# Each module as the dashboard shows it. tests/test_module_layout.py checks that each module has an entry.
CATALOG = {
    "accounts": ModuleInfo(
        "Member accounts",
        "Members connect Canvas, Google and Outlook, and agents read them for the member.",
        needs=(Need("ACCOUNTS_BASE_URL", "ACCOUNTS_BASE_URL setting", kind="setting"),),
    ),
    "agents": ModuleInfo(
        "Agents",
        "Conversations, memories and pending actions of the org's agents.",
        needs=(Need("openrouter", "OpenRouter", optional=True),),
    ),
    "alerts": ModuleInfo("Alerts", "Job and hackathon listings posted to Discord webhooks.", packs=("careers",)),
    "auth": ModuleInfo(
        "Sign-in", "Discord sign-in for officers and members, tokens and access checks.", (DISCORD_BOT,)
    ),
    "bot": ModuleInfo("Discord bot", "The Discord bot that runs the commands of other modules.", (DISCORD_BOT,)),
    "calendar": ModuleInfo(
        "Calendar sync",
        "Syncs a Notion events database to Google Calendar and serves the public events feed.",
        needs=(Need("notion", "Notion"), Need("google", "Google service account")),
    ),
    "compute": ModuleInfo(
        "Member pods", "GPU and CPU pods on the org's RunPod account that members SSH into.", (RUNPOD,)
    ),
    "dashboard": ModuleInfo("Dashboard", "This dashboard: overview, activity, errors, branding and webhooks."),
    "games": ModuleInfo("Games", "Jeopardy games in the org's Discord server.", (DISCORD_BOT,)),
    "integrations": ModuleInfo("Integration tools", "Gives agents the tools of the services that the org connects."),
    "knowledge": ModuleInfo(
        "Knowledge",
        "Pages and documents that agents search, with crawls on a schedule.",
        needs=(
            Need("embeddings", "Embeddings service", optional=True),
            Need("firecrawl", "Firecrawl", optional=True),
        ),
        packs=("asu",),
    ),
    "leetcode": ModuleInfo(
        "LeetCode", "Posts the daily LeetCode question in a Discord channel and checks who solved it.", (DISCORD_BOT,)
    ),
    "mcp": ModuleInfo("MCP", "The MCP server that gives agents and apps the tools of each module."),
    "organizations": ModuleInfo("Organizations", "The org record, module switches, secrets and machine tokens."),
    "packs": ModuleInfo(
        "Packs",
        "Loads content packs: campus pages and live queries for knowledge, and feeds for alerts.",
        needs=(Need("searxng", "Web search (SearXNG)", optional=True),),
        packs=("asu", "careers"),
    ),
    "points": ModuleInfo("Points", "Points, leaderboards and event check-ins."),
    "public": ModuleInfo("Public pages", "Open routes for the leaderboard, the member list and stats."),
    "runpod": ModuleInfo(
        "Hosting",
        "Deploys the org's own apps to a hosting provider, checks their health and rolls them back.",
        needs=(RUNPOD, Need("github", "GitHub", optional=True)),
    ),
    "storefront": ModuleInfo("Store", "A merch store that members pay for with points."),
    "superadmin": ModuleInfo("Superadmin", "Orgs for the whole deployment. Only the superadmin uses it."),
    "uptime": ModuleInfo(
        "Uptime", "Checks the org's sites and Hosting apps on a schedule and sends an event when one goes down or up."
    ),
    "users": ModuleInfo("Member list", "The members of the org and their profile fields."),
}

# The modules that a new org starts with, in addition to Core. Each other module that an org can switch off starts off.
NEW_ORG_MODULES = ("knowledge", "mcp")


# Importing these puts every table in Base.metadata (alembic/env.py, tests/conftest.py)
MODEL_MODULES = [
    "core.audit",
    "core.error_log",
    "core.secrets",
    "core.webhooks",
    "modules.accounts.models",
    "modules.alerts.models",
    "modules.agents.models",
    "modules.auth.models",
    "modules.games.models",
    "modules.knowledge.models",
    "modules.leetcode.models",
    "modules.calendar.models",
    "modules.compute.models",
    "modules.organizations.models",
    "modules.points.models",
    "modules.runpod.models",
    "modules.storefront.models",
    "modules.uptime.models",
    "modules.users.models",
]

# Importing a jobs module registers its jobs with core.jobs
JOB_MODULES = [
    "core.audit",
    "core.error_log",
    "modules.auth.jobs",
    "modules.points.jobs",
    "modules.calendar.jobs",
    "modules.agents.jobs",
    "modules.accounts.jobs",
    "modules.runpod.jobs",
    "modules.knowledge.jobs",
    "modules.packs.jobs",
    "modules.leetcode.jobs",
    "modules.compute.jobs",
    "modules.alerts.jobs",
    "modules.uptime.jobs",
]

# Importing a tools module registers its tools with core.tools
TOOL_MODULES = [
    "modules.organizations.tools",
    "modules.calendar.tools",
    "modules.points.tools",
    "modules.knowledge.tools",
    "modules.runpod.tools",
    "modules.packs.tools",
    "modules.dashboard.tools",
    "modules.alerts.tools",
    "modules.compute.tools",
    "modules.integrations.tools",
    "modules.accounts.tools",
    "modules.uptime.tools",
    "modules.users.tools",
    "modules.storefront.tools",
    "modules.leetcode.tools",
    "packs.asu.signin.tools",
]


def _load(names: list[str]) -> None:
    for name in names:
        importlib.import_module(name)


def load_models() -> None:
    _load(MODEL_MODULES)


def load_jobs() -> None:
    """Every model, then every job. A job can query any table."""
    load_models()
    _load(JOB_MODULES)


def load_tools() -> None:
    """Every model, then every tool. A tool can query any table."""
    load_models()
    _load(TOOL_MODULES)
