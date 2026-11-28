"""An in-process cache with a time to live for each entry, shared by every thread of one process.

Keys are tuples. The first item names the area, such as "points", and the second is usually the org
prefix, so invalidate("points", "soda") drops every entry of that org's points. Concurrent misses on
the same key run the compute function once; the other callers wait for its value. An exception in
the compute function goes to each caller and nothing is cached.

Each process has its own cache. publish(*prefix) drops the entries in this process and, on Postgres,
sends the prefix with NOTIFY on CHANNEL. start_listener() runs a thread that LISTENs and drops the same
entries, so a write in the worker, the MCP server or another API process shows at the next read. On
SQLite there is no NOTIFY: a write in another process shows after the entry's time to live.
"""

import json
import select
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

from core.log import get_logger

T = TypeVar("T")

logger = get_logger(__name__)

MAX_ENTRIES = 512
CHANNEL = "platform_cache"  # also named in the LISTEN statement of _listen_once
LISTEN_POLL_SECONDS = 5.0
RECONNECT_SECONDS = 5.0


class TTLCache:
    """Values by tuple key, each kept for its own number of seconds. The oldest entry goes first when full."""

    def __init__(self, max_entries: int = MAX_ENTRIES) -> None:
        self.max_entries = max_entries
        self._entries: OrderedDict[tuple, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._key_locks: dict[tuple, threading.Lock] = {}

    def get(self, key: tuple[Hashable, ...]) -> tuple[bool, Any]:
        """(True, value) for a live entry, else (False, None)."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False, None
            if entry[0] <= time.monotonic():
                del self._entries[key]
                return False, None
            return True, entry[1]

    def set(self, key: tuple[Hashable, ...], value: Any, ttl: float) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic() + ttl, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def get_or_compute(self, key: tuple[Hashable, ...], ttl: float, compute: Callable[[], T]) -> T:
        """The live value for key, else compute() stored for ttl seconds. One compute runs per key at a time."""
        found, value = self.get(key)
        if found:
            return value
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:
            found, value = self.get(key)
            if found:
                return value
            value = compute()
            self.set(key, value, ttl)
        with self._lock:
            if self._key_locks.get(key) is key_lock and not key_lock.locked():
                del self._key_locks[key]
        return value

    def invalidate(self, *prefix: Hashable) -> int:
        """Drop every entry whose key starts with prefix. No prefix drops every entry. Returns the count."""
        size = len(prefix)
        with self._lock:
            keys = [key for key in self._entries if key[:size] == prefix]
            for key in keys:
                del self._entries[key]
        return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


cache = TTLCache()


def _notify(prefix: tuple[str, ...]) -> None:
    """Send the prefix to every listening process. Does nothing on SQLite. A failure is logged, not raised."""
    from sqlalchemy import text

    from core.db import db_connect

    if db_connect.engine.dialect.name != "postgresql":
        return
    try:
        with db_connect.engine.begin() as conn:
            conn.execute(
                text("SELECT pg_notify(:channel, :payload)"), {"channel": CHANNEL, "payload": json.dumps(prefix)}
            )
    except Exception:
        logger.warning("cache notify failed prefix=%s", prefix, exc_info=True)


def publish(*prefix: str) -> int:
    """Drop the entries under prefix here and in every other process that listens. Returns the count dropped here."""
    dropped = cache.invalidate(*prefix)
    _notify(prefix)
    logger.debug("cache published prefix=%s dropped=%s", prefix, dropped)
    return dropped


def apply_message(payload: str) -> int:
    """Drop the entries under the prefix of a NOTIFY payload, a JSON list of strings. A bad payload drops nothing."""
    try:
        prefix = json.loads(payload)
    except ValueError:
        prefix = None
    if not isinstance(prefix, list) or not prefix or not all(isinstance(part, str) for part in prefix):
        logger.warning("cache message ignored payload=%r", payload[:200])
        return 0
    return cache.invalidate(*prefix)


_listener: threading.Thread | None = None
_listener_lock = threading.Lock()


def _listen_once() -> None:
    """LISTEN on one connection and apply each message until the connection fails."""
    from core.db import db_connect

    raw = db_connect.engine.raw_connection()
    raw.detach()
    conn: Any = raw.dbapi_connection
    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute("LISTEN platform_cache")
        # Messages sent while no connection listened are lost, so every org read is dropped once
        cache.invalidate("org")
        logger.info("cache listener connected channel=%s", CHANNEL)
        if hasattr(conn, "poll"):
            # psycopg2
            while True:
                ready, _, _ = select.select([conn], [], [], LISTEN_POLL_SECONDS)
                if not ready:
                    continue
                conn.poll()
                while conn.notifies:
                    apply_message(conn.notifies.pop(0).payload)
        else:
            # psycopg 3
            while True:
                for notify in conn.notifies(timeout=LISTEN_POLL_SECONDS):
                    apply_message(notify.payload)
    finally:
        conn.close()


def _listen_forever() -> None:
    while True:
        try:
            _listen_once()
        except Exception:
            logger.warning("cache listener lost its connection, retry in %ss", RECONNECT_SECONDS, exc_info=True)
        time.sleep(RECONNECT_SECONDS)


def start_listener() -> threading.Thread | None:
    """Start the LISTEN thread once per process on Postgres. Returns it, or None on SQLite."""
    global _listener
    from core.db import db_connect

    if db_connect.engine.dialect.name != "postgresql":
        return None
    with _listener_lock:
        if _listener is None or not _listener.is_alive():
            _listener = threading.Thread(target=_listen_forever, name="cache-listener", daemon=True)
            _listener.start()
    return _listener
