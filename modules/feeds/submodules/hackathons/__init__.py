"""Upcoming hackathons, as a feed preset and the hackathons kind."""

from core.submodules import Submodule
from modules.feeds.types import Feed

SUBMODULE = Submodule(
    "feeds",
    "hackathons",
    "Hackathons",
    "Upcoming hackathons from Hack Club, Euro-Hackathons and Hackalist.",
    shared=True,
)

# The feeds an officer can add from a preset
FEEDS = (
    Feed(
        key="hackathons",
        title="Hackathons",
        description="Upcoming hackathons from Hack Club, Euro-Hackathons and Hackalist.",
        kind="hackathons",
        every_hours=12,
    ),
)
