"""Sorts tools into layers. No Flask here.

The base domains are the same in every org, and an agent sees their tools in the tool list. The tools of a
service the org connected (GitHub, RunPod, Notion, Google) are in the list under the service's name. A module's
tools sit under the base: an agent finds them with modules.list and runs them with modules.call. Every tool
also runs by its own name.

The guide tool serves the skills in skills/ at the repo root: how to use Platform MCP for a task.
"""

from collections import Counter
from pathlib import Path

import yaml

from core.tools import ToolSpec
from modules.integrations.servers import SERVERS

BASE = ("org", "activity", "members", "access", "connections", "hosting", "modules", "server")
TOP = ("search", "batch", "guide")

ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_FILE = "SKILL.md"
MAX_SKILL = 20_000
GUIDES = ROOT / "skills"


def domain(name: str) -> str:
    return name.split(".", 1)[0]


def is_service(spec: ToolSpec) -> bool:
    """A tool of a connected service: GitHub, RunPod, Notion, Google and the like."""
    return spec.integration is not None and (domain(spec.name) == spec.integration or domain(spec.name) in SERVERS)


def layer(spec: ToolSpec) -> str:
    """base, service or module."""
    if spec.name in TOP or domain(spec.name) in BASE:
        return "base"
    return "service" if is_service(spec) else "module"


def grouped(specs: list[ToolSpec], kind: str) -> dict[str, list[ToolSpec]]:
    """The tools of one layer by domain, in name order."""
    found: dict[str, list[ToolSpec]] = {}
    for spec in sorted(specs, key=lambda s: s.name):
        if layer(spec) == kind:
            found.setdefault(domain(spec.name), []).append(spec)
    return found


def folder(name: str, specs: list[ToolSpec]) -> Path:
    """The folder of a module domain: the module most of its tools belong to, else the domain name."""
    counts = Counter(spec.module for spec in specs if spec.module)
    module = counts.most_common(1)[0][0] if counts else name
    return ROOT / "modules" / module


def skill(name: str, specs: list[ToolSpec]) -> str | None:
    """The SKILL.md of a module domain, or None."""
    path = folder(name, specs) / SKILL_FILE
    return path.read_text()[:MAX_SKILL] if path.is_file() else None


def _front(text: str) -> dict:
    """The YAML frontmatter of a SKILL.md, or {}."""
    if not text.startswith("---\n"):
        return {}
    head = text[4:].split("\n---", 1)[0]
    try:
        found = yaml.safe_load(head)
    except yaml.YAMLError:
        return {}
    return found if isinstance(found, dict) else {}


def guides() -> list[dict]:
    """The skills in skills/: name and description, in name order."""
    found = []
    for path in sorted(GUIDES.glob(f"*/{SKILL_FILE}")):
        front = _front(path.read_text())
        found.append({"name": path.parent.name, "description": str(front.get("description", ""))})
    return found


def guide(name: str) -> str | None:
    """The text of one skill in skills/, or None."""
    if name not in {item["name"] for item in guides()}:
        return None
    return (GUIDES / name / SKILL_FILE).read_text()[:MAX_SKILL]
