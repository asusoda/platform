"""Data types for ASU sources and live queries."""

from collections.abc import Callable
from dataclasses import dataclass

from modules.knowledge.fetch import Fetched

__all__ = ["Fetched", "QueryError", "QueryParam", "QuerySource", "Source"]


@dataclass(frozen=True)
class Source:
    """A public ASU page crawled on a schedule. extractor replaces the generic text extraction."""

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

    def __post_init__(self) -> None:
        if (self.to_url is None) == (self.answer is None):
            raise ValueError(f"query source {self.key} sets exactly one of to_url and answer")


class QueryError(RuntimeError):
    """The query could not be answered; the reason goes back to the caller."""
