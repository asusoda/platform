"""An in-process cache with a time to live for each entry, shared by every thread of one process.

Keys are tuples. The first item names the area, such as "points", and the second is usually the org
prefix, so invalidate("points", "soda") drops every entry of that org's points. Concurrent misses on
the same key run the compute function once; the other callers wait for its value. An exception in
the compute function goes to each caller and nothing is cached.

Each process has its own cache. A write in another process, such as the bot or the MCP server, shows
after the entry's time to live.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

T = TypeVar("T")

MAX_ENTRIES = 512


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
