"""Arizona State University: public ASU pages crawled on a schedule, and live queries against ASU sites."""

from modules.submodules.types import Submodule
from submodules.asu.queries import QUERIES
from submodules.asu.sources import SOURCES

SUBMODULE = Submodule(
    name="asu",
    title="Arizona State University",
    description="Public ASU pages and live queries: library hours, events, courses, dining, scholarships, news, "
    "shuttles, jobs, sports.",
    sources=tuple(SOURCES.values()),
    queries=QUERIES,
    timezone="America/Phoenix",
)
