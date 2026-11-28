"""Sub-modules: parts of a module with their own switch, in modules/<module>/submodules/<name>/. No Flask here.

Each sub-module folder sets SUBMODULE in its __init__.py. modules/manifest.py lists the folders and loads them.
The switch key of a sub-module is <module>.<name>, such as points.store. A sub-module is on only when its module
is on too.
"""

import importlib
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Submodule:
    """A part of a module that an org turns on or off on its own."""

    # The parent module, such as points
    module: str
    # The folder name, such as store
    name: str
    # The name the dashboard shows, such as Store
    title: str
    description: str
    # Content made once for every org, which each org subscribes to
    shared: bool = False
    # Runs when an org turns the sub-module on, with the session and the org id
    on_enable: Callable[[Session, int], None] | None = None

    @property
    def key(self) -> str:
        return f"{self.module}.{self.name}"


# Every loaded sub-module by key
SUBMODULES: dict[str, Submodule] = {}
_LOADED: set[str] = set()


class SubmoduleError(RuntimeError):
    pass


def load(packages: list[str]) -> None:
    """Import each package, such as modules.points.submodules.store, and register its SUBMODULE once."""
    for package in packages:
        if package in _LOADED:
            continue
        found = getattr(importlib.import_module(package), "SUBMODULE", None)
        parts = package.split(".")
        if not isinstance(found, Submodule):
            raise SubmoduleError(f"{package} sets no SUBMODULE")
        if found.name != parts[-1] or found.module != parts[-3]:
            raise SubmoduleError(f"{package} declares {found.key}; the folder gives {parts[-3]}.{parts[-1]}")
        SUBMODULES[found.key] = found
        _LOADED.add(package)


def get(key: str) -> Submodule | None:
    return SUBMODULES.get(key)


def of(module: str) -> list[Submodule]:
    """The sub-modules of a module, in load order."""
    return [s for s in SUBMODULES.values() if s.module == module]
