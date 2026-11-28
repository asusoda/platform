"""The content of the knowledge sub-modules, loaded once per process. No Flask here.

A knowledge sub-module with content has a content.py next to its __init__.py. It sets CONTENT to a
modules.knowledge.content.types.Content, or registers a sign-in. Loading registers the extractors of the crawled
sources with knowledge as <content name>.<source key>.
"""

import importlib
import importlib.util

from core import submodules
from core.submodules import Submodule
from modules.knowledge import extract
from modules.knowledge.content.types import Content
from modules.manifest import load_submodules

# Each content by its name, such as asu, and the sub-module that holds it
CONTENT: dict[str, Content] = {}
OWNER: dict[str, Submodule] = {}


def load() -> None:
    """Load the content of each knowledge sub-module once."""
    if CONTENT:
        return
    load_submodules()
    for sub in submodules.of("knowledge"):
        package = f"modules.knowledge.submodules.{sub.name}.content"
        if importlib.util.find_spec(package) is None:
            continue
        content = getattr(importlib.import_module(package), "CONTENT", None)
        if content is None:
            continue
        if not isinstance(content, Content):
            raise ValueError(f"{package} must set CONTENT to a Content")
        CONTENT[content.name] = content
        OWNER[content.name] = sub
        for source in content.sources:
            name = content.extractor_name(source)
            if name is not None and source.extractor is not None:
                extract.register(name, source.extractor)


def get(name: object) -> Content | None:
    return CONTENT.get(name) if isinstance(name, str) else None


def of(sub: Submodule) -> Content | None:
    """The content a sub-module holds, or None."""
    return next((CONTENT[name] for name, owner in OWNER.items() if owner.key == sub.key), None)


load()
