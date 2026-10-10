"""Run the background job worker (Postgres only).

Runs every job modules declare in their jobs.py, including periodic ones, with retries and run
history in the procrastinate_jobs table. On SQLite there is no queue and the API runs jobs
itself, so this exits.
"""

import sys

from core import jobs
from core.config import config
from core.log import get_logger, init_sentry
from modules.manifest import load_jobs

logger = get_logger(__name__)


def main() -> int:
    init_sentry(config.SENTRY_DSN)
    if jobs.queue_backend() != "procrastinate":
        logger.error("The job worker needs Postgres (DATABASE_URL=postgresql://...); on SQLite the API runs jobs")
        return 1
    load_jobs()
    app = jobs.procrastinate_app()
    logger.info("Starting job worker jobs=%s", ",".join(sorted(jobs.JOBS)))
    with app.open():
        app.run_worker(install_signal_handlers=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
