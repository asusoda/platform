"""ASU term codes, Arizona dates and times, and how a plain course question maps to course parameters."""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from modules.submodules.types import QueryError

#: Arizona keeps UTC-7 all year.
ARIZONA = ZoneInfo("America/Phoenix")

# ASU term codes are 2 plus the two-digit calendar year plus the session digit; Fall 2026 is 2267.
_TERM_DIGIT = {"spring": "1", "summer": "4", "fall": "7"}


def term_code(term: str) -> str:
    """Fall 2026 to 2267. Raises QueryError on anything else."""
    parts = term.strip().split()
    if len(parts) != 2:
        raise QueryError(f"term must look like 'Fall 2026', got {term!r}")
    season, year = parts[0].lower(), parts[1]
    if season not in _TERM_DIGIT:
        raise QueryError(f"term season must be spring, summer or fall, got {parts[0]!r}")
    if not (year.isdigit() and len(year) == 4):
        raise QueryError(f"term year must be four digits, got {year!r}")
    return f"2{year[2:]}{_TERM_DIGIT[season]}"


def day(moment: datetime.datetime) -> str:
    """A moment as the Arizona date it falls on, like Sat Sep 12, 2026."""
    return moment.astimezone(ARIZONA).strftime("%a %b %d, %Y")


def clock(moment: datetime.datetime) -> str:
    """A moment as the Arizona time it falls on, like 3:05 PM."""
    return moment.astimezone(ARIZONA).strftime("%I:%M %p").lstrip("0")


# Plain queries about a course, read into the class search and catalog parameters.

_SEASONS = ("spring", "summer", "fall")

# Words a student writes around a course, which the catalog keyword box cannot match.
_INTENT = frozenset(
    "about any are availability available class classes course courses credit credits description do does enrol "
    "enroll enrollment full get have hours instructor is left many me meet meeting offered open prereq prereqs "
    "prerequisite prerequisites professor requirement requirements room schedule seat seats section sections spots "
    "syllabus take teaches this time times what when where which who".split()
)
_CONNECTIVES = frozenset("a an and for in of the to with".split())
_OPEN = ("open seat", "open section", "seats left", "still open", "spots left", "space left")


def term_for(date: datetime.date) -> str:
    """The term running on date: spring through April, summer through July, fall after it."""
    season = "Spring" if date.month <= 4 else "Summer" if date.month <= 7 else "Fall"
    return f"{season} {date.year}"


def term_in(query: str) -> str | None:
    """The term query names, as the catalog spells it, such as Fall 2026."""
    words = query.split()
    for first, second in zip(words, words[1:], strict=False):
        season = "".join(c for c in first if c.isalnum()).lower()
        year = "".join(c for c in second if c.isdigit())
        if season in _SEASONS and len(year) == 4:
            return f"{season.capitalize()} {year}"
    return None


def _subject(word: str) -> bool:
    return 2 <= len(word) <= 4 and word.isascii() and word.isalpha()


def _number(word: str) -> bool:
    digits = word.rstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return len(digits) == 3 and digits.isdigit() and len(word) - len(digits) <= 1


def code_in(query: str) -> str | None:
    """The course code query names, like CSE 310, written as the catalog spells it."""
    words = [w for w in "".join(c if c.isascii() and c.isalnum() else " " for c in query).split() if w]
    for word in words:
        split = next((i for i, c in enumerate(word) if c.isdigit()), None)
        if split and _subject(word[:split]) and _number(word[split:]):
            return f"{word[:split].upper()} {word[split:]}"
    for first, second in zip(words, words[1:], strict=False):
        if _subject(first) and first.lower() not in _INTENT | _CONNECTIVES and _number(second):
            return f"{first.upper()} {second}"
    return None


def _matchable(word: str) -> bool:
    bare = "".join(c for c in word if c.isalnum()).lower()
    if not bare or bare in _INTENT or bare in _SEASONS:
        return False
    # A four digit number is a year, which the term parameter carries.
    return not (len(bare) == 4 and bare.isdigit())


def class_keywords(query: str) -> str:
    """The course code query names, else the words of it the class search can match."""
    code = code_in(query)
    if code:
        return code
    kept = [w for w in query.split() if _matchable(w)]
    return " ".join(kept) or query.strip()


def class_terms(query: str, today: datetime.date) -> dict[str, str]:
    """The term the query names or the one running today, and open_only when it asks for room."""
    out = {"term": term_in(query) or term_for(today)}
    if any(phrase in query.lower() for phrase in _OPEN):
        out["open_only"] = "true"
    return out


def catalog_keywords(query: str) -> str:
    """The course code query names, else the query."""
    return code_in(query) or query.strip()


def catalog_terms(query: str, _today: datetime.date) -> dict[str, str]:
    """The term the query names, if any."""
    term = term_in(query)
    return {"term": term} if term else {}
