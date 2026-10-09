"""Internship, new grad and hackathon alert feeds for students in the United States."""

from modules.packs.types import Feed, Pack

PACK = Pack(
    name="careers",
    title="Internships and hackathons",
    description="Alert feeds for software internships, new grad roles and upcoming hackathons.",
    feeds=(
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
        Feed(
            key="hackathons",
            title="Hackathons",
            description="Upcoming hackathons from Hack Club, Euro-Hackathons and Hackalist.",
            kind="hackathons",
            every_hours=12,
        ),
    ),
)
