"""ASU pages crawled on a schedule: one module per source with its own extractor, plus static pages."""

from modules.packs.types import Source
from packs.asu.sources import (
    courses,
    dining_hours,
    events,
    jobs,
    library_hours,
    news,
    pages,
    scholarships,
    shuttles,
    sports,
)

_MODULES = (library_hours, events, courses, scholarships, news, shuttles, jobs, sports)

_ALL: tuple[Source, ...] = (
    *(m.SOURCE for m in _MODULES),
    *dining_hours.SOURCES,
    *pages.PAGES,
)

SOURCES: dict[str, Source] = {s.key: s for s in _ALL}

if len(SOURCES) != len(_ALL):
    raise ValueError("two sources share a key")
