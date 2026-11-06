"""The ASU course catalog: the description, credit hours and prerequisites of a course."""

from __future__ import annotations

from typing import Any

from modules.submodules import http
from modules.submodules.params import text, url
from modules.submodules.types import QueryError, QueryParam, QuerySource
from submodules.asu.params import catalog_keywords, catalog_terms, code_in, term_code

_PAGE = "https://catalog.apps.asu.edu/catalog/courses/courselist"
_API = "https://eadvs-cscc-catalog-api.apps.asu.edu/catalog-microservices/api/v1/search/courses"
# The public catalog page sends this header; the API answers Unauthorized without it.
_HEADERS = {"Authorization": "Bearer null"}
#: Courses listed for one keyword search.
MAX_COURSES = 15


def filters(params: dict[str, str]) -> list[tuple[str, str]]:
    """A course code as subject and number, other words as keywords, and the term code.

    The catalog matches keywords against titles and descriptions only, so a code sent as keywords finds nothing.
    """
    keywords = text(params, "keywords")
    code = code_in(keywords)
    subject, number = code.split() if code else ("", "")
    return [
        ("subject", subject),
        ("catalogNbr", number),
        ("keywords", "" if code else keywords),
        ("term", term_code(text(params, "term"))),
    ]


def course_line(course: dict[str, Any]) -> str:
    """One course: code, title, credit hours, prerequisites, and description."""
    head = f"{course.get('SUBJECT', '')} {course.get('CATALOGNBR', '')}: {course.get('COURSETITLELONG', '')}"
    parts = [head.strip(), f"{course.get('HOURS') or '?'} credit hours"]
    colleges = course.get("COLLEGEMAP") or []
    needs = next((c.get("INFO", {}).get("ENROLLREQ") for c in colleges if c.get("INFO", {}).get("ENROLLREQ")), "")
    if needs:
        parts.append(needs)
    if course.get("DESCRLONG"):
        parts.append(http.plain(course["DESCRLONG"], 600))
    return " | ".join(parts)


def answer(params: dict[str, str]) -> tuple[str, str]:
    """The catalog entries that match, read from the JSON the catalog page loads."""
    query = filters(params)
    courses = http.get_json(url(_API, [("refine", "Y"), ("campusOrOnlineSelection", "A"), *query]), _HEADERS)
    if not isinstance(courses, list):
        raise QueryError("the ASU catalog sent no course list")
    if not courses:
        raise QueryError("no course in the ASU catalog matches; try the course code like CSE 310 or fewer words")
    lines = [course_line(c) for c in courses[:MAX_COURSES] if isinstance(c, dict)]
    if len(courses) > MAX_COURSES:
        lines.append(f"[{len(courses) - MAX_COURSES} more courses not shown]")
    return url(_PAGE, query), "\n".join(lines)


QUERY = QuerySource(
    key="course_catalog",
    description=(
        "Look an ASU course up in the catalog: what it covers, its credit hours and prerequisites. "
        "No sections or seats; use courses for those. Example: keywords CSE 340, or keywords machine learning."
    ),
    params=(
        QueryParam("keywords", "Course code like CSE 340, or topic words.", required=True, example="CSE 340"),
        QueryParam("term", "Term the catalog entry is read for. The current term when left out.", example="Fall 2026"),
    ),
    answer=answer,
    category="course_catalog",
    query_param="keywords",
    narrow=catalog_keywords,
    derive=catalog_terms,
)
