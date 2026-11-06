"""ASU live queries: one module per source."""

from modules.submodules import web
from modules.submodules.types import QuerySource
from submodules.asu.queries import (
    campus_map,
    course_catalog,
    courses,
    dining,
    events,
    jobs,
    library_hours,
    news,
    scholarships,
    shuttles,
    social_media,
    sports,
    sports_news,
    study_rooms,
    sun_devil_central,
)

_MODULES = (
    courses,
    course_catalog,
    scholarships,
    events,
    news,
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

QUERIES: tuple[QuerySource, ...] = (
    *(m.QUERY for m in _MODULES),
    sun_devil_central.CLUBS,
    sun_devil_central.CLUB_EVENTS,
)
