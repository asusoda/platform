"""Alert housekeeping, and the events.deliver sender in the worker, which imports every jobs module."""

from datetime import timedelta

from core import webhooks
from core.db import session
from core.jobs import job
from core.log import get_logger
from core.time import utcnow

from . import delivery
from .models import Delivery

logger = get_logger("alerts.jobs")

KEEP_DAYS = 30

webhooks.on_deliver(delivery.send_event)


@job("alerts.prune", cron="20 4 * * *", audit=False)
def prune() -> None:
    """Delete deliveries rows older than KEEP_DAYS."""
    with session() as db:
        deleted = db.query(Delivery).filter(Delivery.created_at < utcnow() - timedelta(days=KEEP_DAYS)).delete()
    logger.info("deliveries pruned rows=%s", deleted)
