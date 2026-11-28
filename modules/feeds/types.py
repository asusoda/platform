"""Values shared by the feed sources and the service."""

from collections.abc import Callable
from dataclasses import dataclass, field

# Fetches a URL and returns the response body as text. Raises SourceError when the request fails.
Fetch = Callable[[str], str]


class SourceError(RuntimeError):
    """A source could not be read now; a later run may succeed."""


@dataclass(frozen=True)
class Item:
    """One thing to announce. key is stable across runs and unique within its feed."""

    key: str
    title: str
    url: str
    fields: list[tuple[str, str]] = field(default_factory=list)
    footer: str = ""


@dataclass(frozen=True)
class Feed:
    """A feed an org can add from a preset: kind and config as put_feed takes them."""

    key: str
    title: str
    description: str
    kind: str
    config: dict = field(default_factory=dict)
    every_hours: int = 3
