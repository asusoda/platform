"""The parameters of a live query, filled from one plain query. No Flask here."""

import datetime
import re

from modules.submodules.types import QueryError, QueryParam, QuerySource

_DATE = re.compile(r"(?<![\d-])(\d{4}-\d{2}-\d{2})(?![\d-])")


def _standalone(text: str, at: int, end: int) -> bool:
    before = text[at - 1] if at > 0 else ""
    after = text[end] if end < len(text) else ""
    return not before.isalnum() and not after.isalnum()


def named(query: str, choices: tuple[str, ...]) -> list[str]:
    """The choices query names as whole words, in declared order. A longer choice wins the words it covers.

    A one-letter choice is never matched, since a word like a is part of most questions.
    """
    lower = query.lower()
    taken: list[tuple[int, int, str]] = []
    for choice in sorted((c for c in choices if len(c) > 1), key=len, reverse=True):
        needle = choice.lower()
        at = lower.find(needle)
        while at != -1 and not _standalone(lower, at, at + len(needle)):
            at = lower.find(needle, at + 1)
        if at == -1:
            continue
        span = (at, at + len(needle))
        if any(span[0] < hi and lo < span[1] for lo, hi, _ in taken):
            continue
        taken.append((*span, choice))
    picked = {choice for _, _, choice in taken}
    return [c for c in choices if c in picked]


_WEEKDAYS = (
    ("monday", "mon"),
    ("tuesday", "tue", "tues"),
    ("wednesday", "wed"),
    ("thursday", "thu", "thur", "thurs"),
    ("friday", "fri"),
    ("saturday",),
    ("sunday",),
)


def dated(query: str, today: datetime.date | None = None) -> str | None:
    """The first valid YYYY-MM-DD in query, else today, tomorrow or the next weekday it names."""
    for found in _DATE.findall(query):
        try:
            return datetime.date.fromisoformat(found).isoformat()
        except ValueError:
            continue
    if today is None:
        return None
    words = {"".join(c for c in w if c.isalpha()) for w in query.lower().split()}
    if "tomorrow" in words:
        return (today + datetime.timedelta(days=1)).isoformat()
    if "today" in words or "tonight" in words:
        return today.isoformat()
    for index, names in enumerate(_WEEKDAYS):
        if words.intersection(names):
            return (today + datetime.timedelta(days=(index - today.weekday()) % 7)).isoformat()
    return None


def _flag(param: QueryParam) -> bool:
    return {c.lower() for c in param.choices} == {"true", "false"}


def fill(source: QuerySource, query: str, today: datetime.date) -> dict[str, str]:
    """The parameters of source as query names them. Raises QueryError naming what the query has to add."""
    texts = [p for p in source.params if not p.choices and not p.date]
    fills = source.query_param or (texts[0].name if texts else None)
    out: dict[str, str] = {}
    for p in source.params:
        if p.name == fills:
            value = source.narrow(query) if source.narrow else query.strip()
        elif p.choices and not _flag(p):
            found = named(query, p.choices)
            value = ",".join(found) if p.many else (found[0] if found else "")
        elif p.date:
            value = dated(query, today) or (today.isoformat() if p.required else "")
        else:
            value = ""
        if value:
            out[p.name] = value
    for name, value in (source.derive(query, today) if source.derive else {}).items():
        if value and name not in out:
            out[name] = value
    missing = [p for p in source.params if p.required and p.name not in out]
    if missing:
        first = missing[0]
        wanted = f"one of: {', '.join(first.choices)}" if first.choices else f"something like {first.example or 'it'}"
        raise QueryError(f"{source.key} needs {', '.join(p.name for p in missing)} in the query; name {wanted}")
    return out
