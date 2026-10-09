"""ASU live queries: one module per source."""

from modules.packs import web
from modules.packs.types import QuerySource
from packs.asu.queries import (
    campus_map,
    course_catalog,
    courses,
    dining,
    events,
    jobs,
    library_catalog,
    library_hours,
    news,
    scholarships,
    shuttles,
    social_media,
    sports,
    sports_news,
    study_rooms,
)

_MODULES = (
    courses,
    course_catalog,
    scholarships,
    events,
    news,
    library_catalog,
    library_hours,
    study_rooms,
    sports,
    sports_news,
    shuttles,
    campus_map,
    social_media,
    dining,
    jobs,
    web,
)

QUERIES: tuple[QuerySource, ...] = tuple(m.QUERY for m in _MODULES)
