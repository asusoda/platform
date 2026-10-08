"""Values shared by the alert sources and the service."""

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
