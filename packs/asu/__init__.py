"""Arizona State University: public ASU pages crawled on a schedule, and live queries against ASU sites."""

from modules.packs.types import Pack
from packs.asu.queries import QUERIES
from packs.asu.sources import SOURCES

PACK = Pack(
    name="asu",
    title="Arizona State University",
    description="Public ASU pages and live queries: library hours, events, courses, dining, scholarships, news, "
    "shuttles, jobs, sports.",
    sources=tuple(SOURCES.values()),
    queries=QUERIES,
    canvas_url="https://canvas.asu.edu",
)
