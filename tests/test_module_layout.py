"""Each module is registered in every place the platform looks, and its docs name its jobs, tools and tables.

A failure message says which file to change. docs/writing-a-module.md lists the places.
"""

import ast
import fnmatch
import importlib
import re
import tomllib
from pathlib import Path

import pytest
from flask import Blueprint

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"
NAMES = sorted(p.name for p in MODULES.iterdir() if (p / "__init__.py").exists())

# The files in modules/ that import Flask. Every other file is in the Flask-free contract in pyproject.toml.
FLASK_FILES = {"api", "member_api", "registry", "cli", "auth.access", "auth.decorators", "auth.routes"}


def _decorator_names(path: Path, decorator: str) -> list[str]:
    """The first string argument of each @decorator(...) in a file."""
    names = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(dec.func, "id", None) == decorator and dec.args:
                    first = dec.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        names.append(first.value)
    return names


def _tables(path: Path) -> list[str]:
    return re.findall(r'__tablename__\s*=\s*"([^"]+)"', path.read_text())


def _surface(name: str) -> list[str]:
    folder = MODULES / name
    found = []
    if (folder / "jobs.py").exists():
        found += _decorator_names(folder / "jobs.py", "job")
    if (folder / "tools.py").exists():
        found += _decorator_names(folder / "tools.py", "tool")
    if (folder / "models.py").exists():
        found += _tables(folder / "models.py")
    return found


@pytest.mark.parametrize("name", NAMES)
def test_manifest_lists_the_module_files(name):
    from modules import manifest

    for file, listed, where in [
        ("models.py", manifest.MODEL_MODULES, "MODEL_MODULES"),
        ("jobs.py", manifest.JOB_MODULES, "JOB_MODULES"),
        ("tools.py", manifest.TOOL_MODULES, "TOOL_MODULES"),
    ]:
        if (MODULES / name / file).exists():
            dotted = f"modules.{name}.{file[:-3]}"
            assert dotted in listed, f"Add {dotted} to {where} in modules/manifest.py"


def test_every_blueprint_is_mounted():
    from modules.registry import MOUNTS

    mounted = {id(mount.blueprint) for mount in MOUNTS}
    for path in sorted(MODULES.glob("*/*api.py")):
        module = importlib.import_module(f"modules.{path.parent.name}.{path.stem}")
        for attr, value in vars(module).items():
            if isinstance(value, Blueprint):
                assert id(value) in mounted, f"Add a Mount for {attr} to MOUNTS in modules/registry.py"


def test_switches_are_optional_modules():
    from core.tools import TOOLS
    from modules.manifest import load_tools
    from modules.organizations.service import OPTIONAL_MODULES
    from modules.registry import MOUNTS

    load_tools()
    switches = [m for mount in MOUNTS for m in [mount.module, *mount.endpoint_modules.values()]]
    switches += [spec.module for spec in TOOLS.values()]
    for module in filter(None, switches):
        assert module in OPTIONAL_MODULES, f"Add {module} to OPTIONAL_MODULES in modules/organizations/service.py"


def test_flask_free_files_are_in_the_contract():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    contract = next(
        c for c in config["tool"]["importlinter"]["contracts"] if c["name"] == "service modules do not import Flask"
    )
    patterns = contract["source_modules"]
    for path in sorted(MODULES.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        dotted = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        if dotted.removeprefix("modules.") in FLASK_FILES or path.stem in FLASK_FILES:
            continue
        covered = any(fnmatch.fnmatchcase(dotted, p) or dotted.startswith(p + ".") for p in patterns)
        assert covered, f"Add {dotted} to the Flask-free contract in pyproject.toml, or import Flask only in api.py"


@pytest.mark.parametrize("name", NAMES)
def test_module_is_documented(name):
    readme = MODULES / name / "README.md"
    assert readme.exists(), f"Add modules/{name}/README.md"
    text = readme.read_text()
    for item in _surface(name):
        assert f"`{item}`" in text, f"Name `{item}` in the Surface list of modules/{name}/README.md"
    assert f"[{name}]({name}/README.md)" in (MODULES / "README.md").read_text(), f"Add {name} to modules/README.md"
    modules_line = next(line for line in (ROOT / "AGENTS.md").read_text().splitlines() if line.startswith("Modules:"))
    assert re.search(rf"\b{name}\b", modules_line), f"Add {name} to the Modules line in AGENTS.md and CLAUDE.md"


def test_data_model_lists_every_table():
    page = (ROOT / "docs" / "data-model.md").read_text()
    for path in [*MODULES.glob("*/models.py"), ROOT / "core" / "audit.py", ROOT / "core" / "secrets.py"]:
        for table in _tables(path):
            assert f"`{table}`" in page, f"Add `{table}` to docs/data-model.md"


def test_agent_files_match():
    claude = (ROOT / "CLAUDE.md").read_text().splitlines()[1:]
    agents = (ROOT / "AGENTS.md").read_text().splitlines()[1:]
    assert claude == agents, "CLAUDE.md and AGENTS.md must have the same text after the title"
