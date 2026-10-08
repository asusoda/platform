"""Background jobs.

Modules declare jobs with @job in their jobs.py and start them with defer(). On Postgres the
jobs go through Procrastinate: defer() writes a row and the worker process (worker_main.py)
runs it, with retries and run history in the procrastinate_jobs table. On SQLite there is no
queue: defer() runs the job in a thread of the calling process and periodic jobs run from a
thread in the API, which is how the platform behaved before the queue existed.
"""

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from croniter import croniter

from core.logging_config import get_logger

logger = get_logger("jobs")


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./data/user.db")


def queue_backend() -> str:
    """'procrastinate' on Postgres, 'inline' otherwise. JOBS_BACKEND overrides it."""
    configured = os.environ.get("JOBS_BACKEND")
    if configured:
        return configured
    return "procrastinate" if _database_url().startswith("postgresql") else "inline"


def _conninfo() -> str:
    url = _database_url()
    scheme, _, rest = url.partition("://")
    return "postgresql://" + rest if scheme.startswith("postgresql") else url


@dataclass
class Job:
    name: str
    func: Callable
    cron: str | None
    retry: int
    task: object | None = None


JOBS: dict[str, Job] = {}

_app = None


def procrastinate_app():
    """The Procrastinate app, created on first use. Only valid with the procrastinate backend."""
    global _app
    if _app is None:
        import procrastinate

        _app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=_conninfo()))
    return _app


def job(name: str, *, cron: str | None = None, retry: int = 0):
    """Register a job. `cron` makes it periodic; `retry` is how many times a failure is retried."""

    def register(func: Callable) -> Callable:
        entry = Job(name=name, func=func, cron=cron, retry=retry)
        if queue_backend() == "procrastinate":
            app = procrastinate_app()
            if cron:

                def periodic(timestamp: int) -> None:
                    func()

                task = app.task(name=name, retry=retry, queueing_lock=name)(periodic)
                app.periodic(cron=cron, periodic_id=name)(task)
            else:
                task = app.task(name=name, retry=retry)(func)
            entry.task = task
        JOBS[name] = entry
        return func

    return register


def _run(entry: Job, kwargs: dict) -> None:
    started = time.monotonic()
    try:
        entry.func(**kwargs)
        logger.info("job finished name=%s seconds=%.2f", entry.name, time.monotonic() - started)
    except Exception:
        logger.exception("job failed name=%s", entry.name)


def defer(name: str, **kwargs) -> threading.Thread | None:
    """Queue a job by name. Returns the thread running it with the inline backend, else None."""
    entry = JOBS[name]
    if entry.task is not None:
        _open_app()
        entry.task.defer(**kwargs)  # type: ignore[attr-defined]
        logger.info("job queued name=%s", name)
        return None
    thread = threading.Thread(target=_run, args=(entry, kwargs), name=f"job-{name}", daemon=True)
    thread.start()
    return thread


_open_lock = threading.Lock()
_app_open = False


def _open_app() -> None:
    """Open the app's sync connection once per process, for defer() calls from web requests."""
    global _app_open
    with _open_lock:
        if not _app_open:
            procrastinate_app().open()
            _app_open = True


def start_inline_scheduler() -> threading.Thread | None:
    """Run periodic jobs from a thread in this process. Only for the inline backend."""
    if queue_backend() != "inline":
        return None
    periodic = [(entry, entry.cron) for entry in JOBS.values() if entry.cron]
    if not periodic:
        return None

    def loop() -> None:
        now = datetime.now(UTC)
        due = {entry.name: croniter(cron, now).get_next(datetime) for entry, cron in periodic}
        while True:
            now = datetime.now(UTC)
            for entry, cron in periodic:
                if due[entry.name] <= now:
                    _run(entry, {})
                    due[entry.name] = croniter(cron, now).get_next(datetime)
            time.sleep(30)

    thread = threading.Thread(target=loop, name="job-scheduler", daemon=True)
    thread.start()
    logger.info("inline job scheduler started jobs=%s", ",".join(entry.name for entry, _ in periodic))
    return thread
