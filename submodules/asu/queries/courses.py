"""The live ASU class search: sections, meeting days, and open seats for one term."""

from __future__ import annotations

from typing import Any

from modules.submodules import http
from modules.submodules.params import choices, code, codes, text, url
from modules.submodules.types import QueryError, QueryParam, QuerySource
from submodules.asu.params import class_keywords, class_terms, code_in, term_code

_PAGE = "https://catalog.apps.asu.edu/catalog/classes/classlist"
_API = "https://eadvs-cscc-catalog-api.apps.asu.edu/catalog-microservices/api/v1/search/classes"
# The public class search page sends this header; the API answers Unauthorized without it.
_HEADERS = {"Authorization": "Bearer null"}
#: Sections listed for one search.
MAX_SECTIONS = 25

_DAYS = {
    "monday": "MON",
    "tuesday": "TUES",
    "wednesday": "WED",
    "thursday": "THURS",
    "friday": "FRI",
    "saturday": "SAT",
    "sunday": "SUN",
}

_LEVELS = {
    "lower division": "lowerdivision",
    "upper division": "upperdivision",
    "undergraduate": "undergrad",
    "graduate": "grad",
    "100-199": "100-199",
    "200-299": "200-299",
    "300-399": "300-399",
    "400-499": "400-499",
}

_SESSIONS = {"a": "A", "b": "B", "c": "C", "other": "DYN"}


def filters(params: dict[str, str]) -> list[tuple[str, str]]:
    """The class search filters. Only term is required; everything else narrows."""
    keywords = text(params, "keywords")
    found = code_in(keywords)
    subject, number = found.split() if found else ("", "")
    return [
        ("campusOrOnlineSelection", "A"),
        ("honors", "F"),
        ("promod", "F"),
        ("term", term_code(text(params, "term"))),
        ("subject", subject),
        ("catalogNbr", number),
        ("keywords", "" if found else keywords),
        ("level", ",".join(codes(params, "level", _LEVELS))),
        ("daysOfWeek", ",".join(codes(params, "days", _DAYS))),
        ("session", code(params, "session", _SESSIONS)),
    ]


def section_line(row: dict[str, Any]) -> str:
    """One section: code, title, class number, days and times, place, instructors, and seats."""
    clas = row.get("CLAS") or {}
    seats = row.get("seatInfo") or {}
    cap, taken = seats.get("ENRL_CAP", clas.get("ENRLCAP")), seats.get("ENRL_TOT", clas.get("ENRLTOT"))
    days = " ".join(d for d in row.get("DAYLIST") or [] if d)
    when = f"{days} {clas.get('STARTTIME') or ''}-{clas.get('ENDTIME') or ''}".strip(" -") if days else "no set times"
    places = ", ".join(p.get("ADDRESS") or p.get("NAME") or "" for p in row.get("LOCATIONBUILDING") or [])
    people = ", ".join(clas.get("INSTRUCTORSLIST") or []) or "staff"
    try:
        left = f"{int(cap) - int(taken)} of {int(cap)} seats open"
    except (TypeError, ValueError):
        left = "seats unknown"
    parts = [
        f"{clas.get('SUBJECT', '')} {clas.get('CATALOGNBR', '')}: {clas.get('TITLE', '')}".strip(),
        f"class {clas.get('CLASSNBR', '?')}",
        when,
        places,
        people,
        left,
    ]
    return " | ".join(p for p in parts if p)


def _open(row: dict[str, Any]) -> bool:
    seats = row.get("seatInfo") or {}
    try:
        return int(seats["ENRL_TOT"]) < int(seats["ENRL_CAP"])
    except (KeyError, TypeError, ValueError):
        return (row.get("CLAS") or {}).get("ENRLSTAT") == "O"


def answer(params: dict[str, str]) -> tuple[str, str]:
    """The sections that match, read from the JSON the class search page loads."""
    query = filters(params)
    found = http.get_json(url(_API, [("refine", "Y"), ("searchType", "all"), ("pageNumber", "1"), *query]), _HEADERS)
    rows = found.get("classes") if isinstance(found, dict) else None
    if not isinstance(rows, list):
        raise QueryError("the ASU class search sent no class list")
    if text(params, "open_only").lower() == "true":
        rows = [r for r in rows if isinstance(r, dict) and _open(r)]
    if not rows:
        raise QueryError(
            "no section matches in that term; try the course code like CSE 310, another term, or fewer words"
        )
    lines = [section_line(r) for r in rows[:MAX_SECTIONS] if isinstance(r, dict)]
    if len(rows) > MAX_SECTIONS:
        lines.append(f"[{len(rows) - MAX_SECTIONS} more sections not shown]")
    return url(_PAGE, [("advanced", "true"), *query]), "\n".join(lines)


QUERY = QuerySource(
    key="courses",
    description=(
        "Search ASU classes for one term: sections, class numbers, instructors, days, rooms, and open seats. "
        "Example: keywords CSE 310, term Spring 2027, open_only true."
    ),
    params=(
        QueryParam("term", "Term to search.", required=True, example="Fall 2026"),
        QueryParam("keywords", "Course code like CSE 310, a subject, or title words.", example="CSE 310"),
        QueryParam("level", "Course levels.", choices=choices(_LEVELS), many=True),
        QueryParam("days", "Meeting days.", choices=choices(_DAYS), many=True),
        QueryParam("session", "Session within the term.", choices=choices(_SESSIONS)),
        QueryParam("open_only", "Only sections with open seats.", choices=("true", "false")),
    ),
    answer=answer,
    category="courses",
    query_param="keywords",
    narrow=class_keywords,
    derive=class_terms,
)
