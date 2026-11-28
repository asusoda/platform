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
# Each sub-module folder, modules/<module>/submodules/<name>/, by its key <module>.<name>
SUBMODULE_DIRS = {
    f"{p.parent.parent.name}.{p.name}": p
    for p in sorted(MODULES.glob("*/submodules/*"))
    if (p / "__init__.py").exists()
}
SUBMODULE_KEYS = sorted(SUBMODULE_DIRS)
# Packages next to modules/ that hold a layer, such as hosting/
LAYER_NAMES = ["hosting"]

# The files in modules/ and the layers that import Flask. Every other file is in the Flask-free contract in
# pyproject.toml.
FLASK_FILES = {"api", "member_api", "officer_api", "registry", "cli", "auth.access", "auth.decorators", "auth.routes"}


def _folder(name: str) -> Path:
    """The folder of a module, a sub-module key or a layer."""
    if name in LAYER_NAMES:
        return ROOT / name
    return SUBMODULE_DIRS.get(name) or MODULES / name


def _dotted(folder: Path) -> str:
    return ".".join(folder.relative_to(ROOT).parts)


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
    folder = _folder(name)
    found = []
    if (folder / "jobs.py").exists():
        found += _decorator_names(folder / "jobs.py", "job")
    if (folder / "tools.py").exists():
        found += _decorator_names(folder / "tools.py", "tool")
    if (folder / "models.py").exists():
        found += _tables(folder / "models.py")
    return found


@pytest.mark.parametrize("name", [*NAMES, *SUBMODULE_KEYS, *LAYER_NAMES])
def test_manifest_lists_the_module_files(name):
    from modules import manifest

    folder = _folder(name)
    for file, listed, where in [
        ("models.py", manifest.MODEL_MODULES, "MODEL_MODULES"),
        ("jobs.py", manifest.JOB_MODULES, "JOB_MODULES"),
        ("tools.py", manifest.TOOL_MODULES, "TOOL_MODULES"),
    ]:
        if (folder / file).exists():
            dotted = f"{_dotted(folder)}.{file[:-3]}"
            assert dotted in listed, f"Add {dotted} to {where} in modules/manifest.py"


def test_every_blueprint_is_mounted():
    from modules.registry import MOUNTS

    mounted = {id(mount.blueprint) for mount in MOUNTS}
    paths = [*MODULES.glob("*/*api.py"), *MODULES.glob("*/submodules/*/*api.py")]
    paths += [path for name in LAYER_NAMES for path in (ROOT / name).glob("*api.py")]
    for path in sorted(paths):
        module = importlib.import_module(".".join(path.relative_to(ROOT).with_suffix("").parts))
        for attr, value in vars(module).items():
            if isinstance(value, Blueprint):
                assert id(value) in mounted, f"Add a Mount for {attr} to MOUNTS in modules/registry.py"


def test_switches_are_optional_modules():
    from core.tools import TOOLS
    from modules.manifest import load_tools
    from modules.organizations.service import switch_keys
    from modules.registry import MOUNTS

    load_tools()
    switches = [m for mount in MOUNTS for m in [mount.module, *mount.endpoint_modules.values()]]
    switches += [spec.module for spec in TOOLS.values()]
    keys = switch_keys()
    for module in filter(None, switches):
        assert module in keys, f"Add {module} to OPTIONAL_MODULES in modules/organizations/service.py, or SUBMODULES"


@pytest.mark.parametrize("key", SUBMODULE_KEYS)
def test_submodule_is_declared(key):
    from core import submodules
    from modules.manifest import SUBMODULES, load_submodules

    module, name = key.split(".")
    assert name in SUBMODULES.get(module, ()), f"Add {name} to SUBMODULES[{module!r}] in modules/manifest.py"
    load_submodules()
    found = submodules.get(key)
    assert found is not None and (found.module, found.name) == (module, name), (
        f"Set SUBMODULE = Submodule({module!r}, {name!r}, ...) in {_folder(key).relative_to(ROOT)}/__init__.py"
    )
    assert found.title and found.description, f"Give {key} a title and a description in its SUBMODULE"


def test_manifest_submodules_have_folders():
    from modules.manifest import SUBMODULES

    for module, names in SUBMODULES.items():
        for name in names:
            assert f"{module}.{name}" in SUBMODULE_DIRS, f"SUBMODULES names {module}.{name}; add its folder"


def test_no_old_sub_module_folders():
    for old in ("submodules", "modules/submodules"):
        assert not (ROOT / old).exists(), f"{old}/ is gone; a sub-module lives in modules/<module>/submodules/<name>/"


def test_hosting_is_a_layer_in_no_category():
    from modules.manifest import CATEGORIES, LAYERS

    assert list(LAYERS) == LAYER_NAMES
    for name in LAYER_NAMES:
        assert not (MODULES / name).exists(), f"{name} is a layer; it has no folder in modules/"
        assert not any(name in names for names in CATEGORIES.values()), f"{name} is a layer, not in a category"
        assert (ROOT / name / "README.md").exists(), f"Add {name}/README.md"
        assert f"[{name}](../{name}/README.md)" in (MODULES / "README.md").read_text(), (
            f"Link {name} in modules/README.md"
        )


def test_flask_free_files_are_in_the_contract():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    contract = next(
        c for c in config["tool"]["importlinter"]["contracts"] if c["name"] == "service modules do not import Flask"
    )
    patterns = contract["source_modules"]
    paths = [*MODULES.rglob("*.py"), *(path for name in LAYER_NAMES for path in (ROOT / name).rglob("*.py"))]
    for path in sorted(paths):
        if path.name == "__init__.py":
            continue
        dotted = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        if dotted.removeprefix("modules.") in FLASK_FILES or path.stem in FLASK_FILES:
            continue
        covered = any(fnmatch.fnmatchcase(dotted, p) or dotted.startswith(p + ".") for p in patterns)
        assert covered, f"Add {dotted} to the Flask-free contract in pyproject.toml, or import Flask only in api.py"


@pytest.mark.parametrize("name", NAMES)
def test_module_has_a_category(name):
    from modules.manifest import CATEGORIES

    found = [category for category, names in CATEGORIES.items() if name in names]
    assert len(found) == 1, f"Put {name} in one category of CATEGORIES in modules/manifest.py"
    readme = (MODULES / "README.md").read_text()
    section = readme.split(f"## {found[0]}\n", 1)[1].split("\n## ", 1)[0]
    assert f"[{name}]({name}/README.md)" in section, f"Move {name} under ## {found[0]} in modules/README.md"


@pytest.mark.parametrize("name", NAMES)
def test_module_has_a_catalog_entry(name):
    from modules.manifest import CATALOG

    info = CATALOG.get(name)
    assert info is not None, f"Add {name} to CATALOG in modules/manifest.py"
    assert info.title and info.description, f"Give {name} a title and a description in CATALOG in modules/manifest.py"


def test_catalog_names_real_modules_and_new_org_modules():
    from modules.manifest import CATALOG, CATEGORIES, CORE, NEW_ORG_MODULES

    for name in CATALOG:
        assert name in NAMES, f"{name} in CATALOG has no folder in modules/"
    for name in NEW_ORG_MODULES:
        assert name in CATALOG and name not in CATEGORIES[CORE], f"{name} in NEW_ORG_MODULES is not an optional module"


def test_categories_name_real_modules_or_submodules():
    from modules.manifest import CATEGORIES

    for category, names in CATEGORIES.items():
        for name in names:
            assert name in NAMES or name in SUBMODULE_KEYS, (
                f"{name} in CATEGORIES[{category!r}] is not a folder in modules/ or a sub-module key"
            )


@pytest.mark.parametrize("name", NAMES)
def test_module_is_documented(name):
    readme = MODULES / name / "README.md"
    assert readme.exists(), f"Add modules/{name}/README.md"
    text = readme.read_text()
    for item in _surface(name):
        assert f"`{item}`" in text, f"Name `{item}` in the Surface list of modules/{name}/README.md"
    assert f"[{name}]({name}/README.md)" in (MODULES / "README.md").read_text(), f"Add {name} to modules/README.md"
    modules_line = next(line for line in (ROOT / "AGENTS.md").read_text().splitlines() if line.startswith("Modules:"))
    assert re.search(rf"\b{name}\b", modules_line), f"Add {name} to the Modules line in AGENTS.md"


@pytest.mark.parametrize("name", [*SUBMODULE_KEYS, *LAYER_NAMES])
def test_submodule_and_layer_are_documented(name):
    folder = _folder(name)
    where = folder.relative_to(ROOT)
    readme = folder / "README.md"
    assert readme.exists(), f"Add {where}/README.md"
    text = readme.read_text()
    for item in _surface(name):
        assert f"`{item}`" in text, f"Name `{item}` in the Surface list of {where}/README.md"
    link = f"({folder.relative_to(MODULES)}/README.md)" if name in SUBMODULE_DIRS else f"(../{name}/README.md)"
    assert link in (MODULES / "README.md").read_text(), f"Link {where}/README.md in modules/README.md"


def test_data_model_lists_every_table():
    page = (ROOT / "docs" / "data-model.md").read_text()
    core_tables = [
        ROOT / "core" / name for name in ("audit.py", "error_log.py", "secrets.py", "submodules.py", "webhooks.py")
    ]
    models = [*MODULES.glob("*/models.py"), *MODULES.glob("*/submodules/*/models.py"), ROOT / "hosting" / "models.py"]
    for path in [*models, *core_tables]:
        for table in _tables(path):
            assert f"`{table}`" in page, f"Add `{table}` to docs/data-model.md"


def test_claude_files_are_links():
    assert (ROOT / "CLAUDE.md").readlink() == Path("AGENTS.md"), "CLAUDE.md must be a link to AGENTS.md"
    assert (ROOT / ".claude").readlink() == Path(".agents"), ".claude must be a link to .agents"


def test_each_module_with_tools_has_a_skill():
    from core.tools import TOOLS
    from modules import manifest
    from modules.mcp import layers

    manifest.load_tools()
    for name, specs in layers.grouped(list(TOOLS.values()), "module").items():
        path = layers.folder(name, specs) / layers.SKILL_FILE
        assert path.is_file(), f"Add {path.relative_to(ROOT)}: modules.skill gives it to agents for the {name} tools"
        assert path.read_text().startswith(f"---\nname: {name}\n"), f"{path.relative_to(ROOT)} starts with name: {name}"
