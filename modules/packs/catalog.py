"""The packs in the packs/ folder, loaded once per process. No Flask here.

Each folder in packs/ is one pack. Its __init__.py sets PACK to a modules.packs.types.Pack. Loading a
pack registers the extractors of its crawled sources with knowledge as <pack>.<source key>.
"""

import importlib
import pkgutil

import packs as packs_folder
from modules.knowledge import extract
from modules.packs.types import Pack

PACKS: dict[str, Pack] = {}


def _load() -> None:
    for info in sorted(pkgutil.iter_modules(packs_folder.__path__), key=lambda i: i.name):
        if not info.ispkg or info.name.startswith("_"):
            continue
        pack = getattr(importlib.import_module(f"packs.{info.name}"), "PACK", None)
        if not isinstance(pack, Pack):
            raise ValueError(f"packs/{info.name}/__init__.py must set PACK to a Pack")
        if pack.name != info.name:
            raise ValueError(f"packs/{info.name} sets PACK.name to {pack.name}; use the folder name")
        PACKS[pack.name] = pack
        for source in pack.sources:
            name = pack.extractor_name(source)
            if name is not None and source.extractor is not None:
                extract.register(name, source.extractor)


def get(name: object) -> Pack | None:
    return PACKS.get(name) if isinstance(name, str) else None


_load()
