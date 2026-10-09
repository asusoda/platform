"""The shared in-process cache in core/cache.py."""

import threading
import time

import pytest

from core.cache import TTLCache


def test_value_is_kept_until_its_ttl():
    cache = TTLCache()
    cache.set(("org", "soda", "a"), 1, ttl=0.05)
    assert cache.get(("org", "soda", "a")) == (True, 1)
    time.sleep(0.06)
    assert cache.get(("org", "soda", "a")) == (False, None)


def test_invalidate_drops_keys_with_the_prefix():
    cache = TTLCache()
    cache.set(("org", "soda", "a"), 1, ttl=60)
    cache.set(("org", "ais", "a"), 2, ttl=60)
    cache.set(("access", "x"), 3, ttl=60)
    assert cache.invalidate("org", "soda") == 1
    assert cache.get(("org", "ais", "a")) == (True, 2)
    assert cache.invalidate("org") == 1
    assert cache.get(("access", "x")) == (True, 3)


def test_oldest_entry_goes_first_when_full():
    cache = TTLCache(max_entries=2)
    for i in range(3):
        cache.set(("k", i), i, ttl=60)
    assert cache.get(("k", 0)) == (False, None)
    assert cache.get(("k", 2)) == (True, 2)


def test_concurrent_misses_compute_once():
    cache = TTLCache()
    calls = []
    started = threading.Event()

    def compute():
        calls.append(1)
        started.set()
        time.sleep(0.05)
        return "value"

    results = []
    threads = [
        threading.Thread(target=lambda: results.append(cache.get_or_compute(("k",), 60, compute))) for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == ["value"] * 8
    assert len(calls) == 1


def test_an_exception_is_not_cached():
    cache = TTLCache()

    def fail():
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        cache.get_or_compute(("k",), 60, fail)
    assert cache.get_or_compute(("k",), 60, lambda: "ok") == "ok"
