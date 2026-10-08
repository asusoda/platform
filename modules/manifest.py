"""The modules that hold models, jobs and tools. Flask-free, so alembic, the worker and MCP can load it."""

import importlib

# Importing these puts every table in Base.metadata (alembic/env.py, tests/conftest.py)
MODEL_MODULES = [
    "core.audit",
    "core.secrets",
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
    "modules.users.models",
]

# Importing a jobs module registers its jobs with core.jobs
JOB_MODULES = [
    "core.audit",
    "modules.auth.jobs",
    "modules.points.jobs",
    "modules.calendar.jobs",
    "modules.agents.jobs",
    "modules.accounts.jobs",
    "modules.runpod.jobs",
    "modules.knowledge.jobs",
    "modules.asu.jobs",
    "modules.leetcode.jobs",
    "modules.compute.jobs",
    "modules.alerts.jobs",
]

# Importing a tools module registers its tools with core.tools
TOOL_MODULES = [
    "modules.organizations.tools",
    "modules.calendar.tools",
    "modules.points.tools",
    "modules.knowledge.tools",
    "modules.runpod.tools",
    "modules.asu.tools",
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
