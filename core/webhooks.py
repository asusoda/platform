"""Events: what modules send, saved as notifications and handed to the senders (the alerts module).

A module declares its events with declare() and sends one with emit(). emit() never raises and returns at once:
it queues the events.deliver job. The job saves the event as a notification of the org, then calls each handler
that on_deliver() added. modules/alerts/jobs.py adds the one that posts to the org's destinations; every process
(API, bot, MCP server, worker) loads it at start with modules.manifest.load_jobs(), as the inline queue runs a
job in the process that queued it. The org keeps the notifications of the last KEEP_DAYS days, at most
KEEP_COUNT. An emit() from inside events.deliver does nothing, so an error logged while delivering cannot queue
another delivery. No Flask here.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, column
from sqlalchemy import table as sql_table
from sqlalchemy.orm import Mapped, mapped_column

from core import jobs
from core.db import Base, session
from core.log import get_logger
from core.time import utcnow

logger = get_logger("events")

DELIVER_JOB = "events.deliver"
KEEP_DAYS = 30
KEEP_COUNT = 200
RED = 0xE5484D
GREEN = 0x30A46C
BLUE = 0x3E63DD
AMBER = 0xF5A524


@dataclass(frozen=True)
class Event:
    key: str
    label: str
    description: str
    # The optional module that sends the event. The event is listed and sent only when the org has the module on.
    module: str | None = None


@dataclass(frozen=True)
class Message:
    """One event or post as text. Each kind of destination turns it into the body its service reads."""

    title: str
    text: str = ""
    fields: tuple[tuple[str, str], ...] = ()
    url: str | None = None
    color: int = BLUE
    footer: str | None = None
    # ISO 8601 time shown on the message, such as when a feed item was found
    timestamp: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """The message from asdict(), after a trip through the job queue as JSON."""
        return cls(
            title=str(data["title"]),
            text=str(data.get("text") or ""),
            fields=tuple((str(name), str(value)) for name, value in data.get("fields") or ()),
            url=data.get("url"),
            color=int(data.get("color", BLUE)),
            footer=data.get("footer"),
            timestamp=data.get("timestamp"),
        )


EVENTS: dict[str, Event] = {}
# Called by events.deliver with (org_id or None, event, message, server)
Handler = Callable[[int | None, str, Message, bool], None]
_handlers: list[Handler] = []


def declare(key: str, label: str, description: str, module: str | None = None) -> None:
    """Add an event that officers can pick for a destination."""
    EVENTS[key] = Event(key, label, description, module)


def on_deliver(handler: Handler) -> None:
    """Add a handler that events.deliver calls for each event. Adding the same handler again does nothing."""
    if handler not in _handlers:
        _handlers.append(handler)


class Notification(Base):
    """One event that an org's officers see in Notifications, whether or not a destination takes it."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    color: Mapped[int] = mapped_column(Integer, nullable=False, default=BLUE)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, index=True)


declare("job.failed", "Failed job runs", "A background job for the org fails, such as a crawl or a reindex.")

_organizations = sql_table("organizations", column("id"), column("prefix"), column("config", JSON))


def emit(org: int | str | None, event: str, message: Message, server: bool = False) -> None:
    """Queue the event for the org (an id or a prefix). server also sends it to ERROR_WEBHOOK_URL. Never raises."""
    if (org is None or org == "") and not server:
        return
    if event not in EVENTS:
        logger.warning("event not declared event=%s", event)
        return
    if jobs.current_job.get() == DELIVER_JOB:
        logger.info("event skipped inside %s event=%s org=%s", DELIVER_JOB, event, org)
        return
    try:
        jobs.defer(DELIVER_JOB, org=org or None, event=event, message=asdict(message), server=server)
    except Exception as e:
        logger.warning("event not queued event=%s org=%s error=%s: %s", event, org, type(e).__name__, e)


def _org_id(db, org: int | str) -> int | None:
    if isinstance(org, int):
        return org
    row = db.execute(_organizations.select().where(_organizations.c.prefix == org)).first()
    return int(row.id) if row is not None else None


def save(db, org_id: int, event: str, message: Message) -> None:
    """Add the event as a notification of the org and drop the org's old ones. The caller commits."""
    text = "\n".join([message.text, *(f"{name}: {value}" for name, value in message.fields)]).strip()
    db.add(
        Notification(
            organization_id=org_id, event=event, title=message.title[:256], text=text[:2000], color=message.color
        )
    )
    db.flush()
    mine = db.query(Notification).filter_by(organization_id=org_id)
    mine.filter(Notification.created_at < utcnow() - timedelta(days=KEEP_DAYS)).delete()
    # Only rows older than the oldest kept one go, so a row that another delivery commits meanwhile stays
    kept = [i for (i,) in mine.order_by(Notification.id.desc()).with_entities(Notification.id).limit(KEEP_COUNT)]
    if len(kept) == KEEP_COUNT:
        mine.filter(Notification.id < kept[-1]).delete(synchronize_session=False)


@jobs.job(DELIVER_JOB, audit=False)
def deliver(org: int | str | None, event: str, message: dict, server: bool = False) -> None:
    """Save the event as a notification, then call each handler. Never raises, so it sends no job.failed itself."""
    parsed = Message.from_dict(message)
    org_id = None
    try:
        if org is not None:
            with session() as db:
                org_id = _org_id(db, org)
                if org_id is None:
                    logger.warning("event for an unknown org event=%s org=%s", event, org)
                else:
                    save(db, org_id, event, parsed)
    except Exception as e:
        logger.warning("notification not saved event=%s org=%s error=%s: %s", event, org, type(e).__name__, e)
    if org_id is None and not server:
        return
    if not _handlers:
        logger.warning("no event handler in this process event=%s; the process did not call load_jobs()", event)
    for handler in _handlers:
        try:
            handler(org_id, event, parsed, server)
        except Exception as e:
            logger.warning(
                "event handler failed event=%s org=%s handler=%s error=%s: %s",
                event,
                org_id,
                getattr(handler, "__qualname__", handler),
                type(e).__name__,
                e,
            )
