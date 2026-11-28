"""Helpers that map query parameters to URL values, after queries.check has validated them."""

from __future__ import annotations

import urllib.parse
from collections.abc import Iterable


def text(params: dict[str, str], name: str) -> str:
    """The value of name with surrounding whitespace removed, or empty."""
    return params.get(name, "").strip()


def codes(params: dict[str, str], name: str, mapping: dict[str, str]) -> list[str]:
    """The codes of a comma-separated list of choices."""
    return [mapping[v.strip().lower()] for v in text(params, name).split(",") if v.strip()]


def code(params: dict[str, str], name: str, mapping: dict[str, str]) -> str:
    """The code of a single choice, or empty when the parameter is absent."""
    value = text(params, name).lower()
    return mapping[value] if value else ""


def choices(mapping: dict[str, str]) -> tuple[str, ...]:
    """The choices a mapping accepts, in order."""
    return tuple(mapping)


def url(base: str, pairs: Iterable[tuple[str, str]]) -> str:
    """base with every non-empty pair as a query parameter, in order, repeats kept."""
    kept = [(k, v) for k, v in pairs if v]
    return f"{base}?{urllib.parse.urlencode(kept)}" if kept else base
