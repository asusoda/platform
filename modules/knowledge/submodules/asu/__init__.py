"""Arizona State University: shared ASU pages that knowledge search reads, and live queries against ASU sites."""

from core.submodules import Submodule


def _enable(db, org_id: int) -> None:
    """Bring the shared ASU pages up to date and start the crawl of the due ones."""
    from modules.knowledge import crawl, shared
    from modules.knowledge.submodules.asu.content import CONTENT

    shared.sync_shared(db, SUBMODULE, CONTENT)
    db.commit()
    crawl.start_crawl_due()


SUBMODULE = Submodule(
    "knowledge",
    "asu",
    "Arizona State University",
    "Public ASU pages and live queries: library hours, events, courses, dining, scholarships, news, shuttles, jobs, "
    "sports.",
    shared=True,
    on_enable=_enable,
)
