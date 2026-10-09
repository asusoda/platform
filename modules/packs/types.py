"""Data types for packs: crawled sources, live queries and the pack itself."""

from collections.abc import Callable
from dataclasses import dataclass

from modules.knowledge.fetch import Fetched

__all__ = ["Fetched", "Pack", "QueryError", "QueryParam", "QuerySource", "Source"]


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
    """One parameter a live query takes. choices restrict the input; many allows a comma list."""

    name: str
    description: str
    required: bool = False
    example: str | None = None
    choices: tuple[str, ...] = ()
    many: bool = False


@dataclass(frozen=True)
class QuerySource:
    """A source queried live with parameters. Exactly one of to_url and answer is set."""

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

    def __post_init__(self) -> None:
        if (self.to_url is None) == (self.answer is None):
            raise ValueError(f"query source {self.key} sets exactly one of to_url and answer")


class QueryError(RuntimeError):
    """The query could not be answered; the reason goes back to the caller."""


@dataclass(frozen=True)
class Pack:
    """A named set of crawled sources and live queries that an org adds to its knowledge in one step.

    name is lowercase letters, digits and underscores. The pack owns the org's knowledge sources whose
    keys start with name/ (crawled pages) and name-live/ (indexed live results).
    """

    name: str
    title: str
    description: str
    sources: tuple[Source, ...] = ()
    queries: tuple[QuerySource, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not all(c.islower() or c.isdigit() or c == "_" for c in self.name):
            raise ValueError(f"pack name {self.name!r} must be lowercase letters, digits and underscores")
        for kind, keys in (("source", [s.key for s in self.sources]), ("query", [q.key for q in self.queries])):
            if len(keys) != len(set(keys)):
                raise ValueError(f"two {kind}s of pack {self.name} share a key")

    @property
    def key_prefix(self) -> str:
        return f"{self.name}/"

    @property
    def live_prefix(self) -> str:
        return f"{self.name}-live/"

    def extractor_name(self, source: Source) -> str | None:
        return f"{self.name}.{source.key}" if source.extractor is not None else None
