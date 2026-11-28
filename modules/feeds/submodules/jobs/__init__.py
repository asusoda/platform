"""Software internship and new grad roles from GitHub job lists, as feed presets and the github_jobs kind."""

from core.submodules import Submodule
from modules.feeds.types import Feed

SUBMODULE = Submodule(
    "feeds",
    "jobs",
    "Job alerts",
    "New software internship and new grad roles from GitHub job lists.",
    shared=True,
)

# The feeds an officer can add from a preset
FEEDS = (
    Feed(
        key="internships",
        title="Software internships",
        description="New rows in the Summer 2026 internship list that vanshb03 keeps on GitHub.",
        kind="github_jobs",
        config={"repo": "vanshb03/Summer2026-Internships", "label": "Internship"},
    ),
    Feed(
        key="new-grad",
        title="New grad roles",
        description="New rows in the 2026 new grad list that vanshb03 keeps on GitHub.",
        kind="github_jobs",
        config={"repo": "vanshb03/New-Grad-2026", "label": "New grad"},
    ),
)
