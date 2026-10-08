"""Named text extractors for crawled sources whose pages need more than the generic extraction.

A module registers an extractor under a name and sets that name on its sources. Extractors are
registered when the module is imported; modules/registry.py imports every job module, so a
worker has them before any crawl runs.
"""

from collections.abc import Callable

from modules.knowledge.fetch import Fetched

EXTRACTORS: dict[str, Callable[[Fetched], str]] = {}


def register(name: str, func: Callable[[Fetched], str]) -> None:
    EXTRACTORS[name] = func


def get(name: str | None) -> Callable[[Fetched], str] | None:
    return EXTRACTORS.get(name) if name else None
