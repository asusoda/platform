"""Data types for submodules: crawled sources, live queries and the submodule itself."""

import datetime
from collections.abc import Callable
from dataclasses import dataclass, field

from modules.knowledge.fetch import Fetched

__all__ = ["Feed", "Fetched", "Submodule", "QueryError", "QueryParam", "QuerySource", "Source"]


@dataclass(frozen=True)
class Source:
    """A public page crawled on a schedule. extractor replaces the generic text extraction."""

    key: str
    url: str
    category: str
    fetch_every_hours: int = 24
    needs_js: bool = False
    extractor: Callable[[Fetched], str] | None = None


@dataclass(frozen=True)
class QueryParam:
    """One parameter a live query takes. choices restrict the input; many allows a comma list; date takes YYYY-MM-DD."""

    name: str
    description: str
    required: bool = False
    example: str | None = None
    choices: tuple[str, ...] = ()
    many: bool = False
    date: bool = False


@dataclass(frozen=True)
class QuerySource:
    """A source queried live with parameters. Exactly one of to_url and answer is set.

    search fills the parameters from one query: query_param names the text parameter the query fills (else the first
    one), narrow cuts the words the source cannot match, and derive gives values the query implies.
    """

    key: str
    description: str
    params: tuple[QueryParam, ...]
    to_url: Callable[[dict[str, str]], str] | None = None
    needs_js: bool = False
    extractor: Callable[[Fetched], str] | None = None
    answer: Callable[[dict[str, str]], tuple[str, str]] | None = None
    category: str = "live"
    index: bool = True
    needs_search: bool = False
    query_param: str | None = None
    narrow: Callable[[str], str] | None = None
    derive: Callable[[str, datetime.date], dict[str, str]] | None = None

    def __post_init__(self) -> None:
        if (self.to_url is None) == (self.answer is None):
            raise ValueError(f"query source {self.key} sets exactly one of to_url and answer")


class QueryError(RuntimeError):
    """The query could not be answered; the reason goes back to the caller."""


@dataclass(frozen=True)
class Feed:
    """An alert feed an org can add: kind and config as the alerts module takes them."""

    key: str
    title: str
    description: str
    kind: str
    config: dict = field(default_factory=dict)
    every_hours: int = 3


@dataclass(frozen=True)
class Submodule:
    """Content for one campus or topic: crawled pages and live queries for knowledge, and alert feeds.

    name is lowercase letters, digits and underscores. The submodule owns the org's knowledge sources whose
    keys start with name/ (crawled pages) and name-live/ (indexed live results).
    """

    name: str
    title: str
    description: str
    sources: tuple[Source, ...] = ()
    queries: tuple[QuerySource, ...] = ()
    feeds: tuple[Feed, ...] = ()
    # IANA time zone a query that names no date is read in
    timezone: str = "UTC"

    def __post_init__(self) -> None:
        if not self.name or not all(c.islower() or c.isdigit() or c == "_" for c in self.name):
            raise ValueError(f"submodule name {self.name!r} must be lowercase letters, digits and underscores")
        kinds = (
            ("source", [s.key for s in self.sources]),
            ("query", [q.key for q in self.queries]),
            ("feed", [f.key for f in self.feeds]),
        )
        for kind, keys in kinds:
            if len(keys) != len(set(keys)):
                raise ValueError(f"two {kind}s of submodule {self.name} share a key")

    @property
    def key_prefix(self) -> str:
        return f"{self.name}/"

    @property
    def live_prefix(self) -> str:
        return f"{self.name}-live/"

    def extractor_name(self, source: Source) -> str | None:
        return f"{self.name}.{source.key}" if source.extractor is not None else None
