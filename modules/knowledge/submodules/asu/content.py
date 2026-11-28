"""The ASU content: public ASU pages crawled on a schedule, and live queries against ASU sites."""

from modules.knowledge.content.types import Content
from modules.knowledge.submodules.asu.queries import QUERIES
from modules.knowledge.submodules.asu.sources import SOURCES

CONTENT = Content(
    name="asu",
    sources=tuple(SOURCES.values()),
    queries=QUERIES,
    timezone="America/Phoenix",
)
