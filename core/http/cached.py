"""Cached JSON responses for org-scoped reads, with an ETag, and the hook that drops them after a write.

A cached response is kept under the key ("org", prefix, ...) in core/cache.py. The access check of the
route runs before the cache is read, so the cache only answers callers that the route lets through.
Each response has Cache-Control: private, no-cache: the browser keeps it, asks again each time, and gets
304 with no body when the ETag still matches.
"""

import hashlib
from collections.abc import Callable, Hashable
from typing import Any

from flask import Flask, Response, current_app, request

from core.cache import cache
from core.log import get_logger

logger = get_logger(__name__)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def org_key(org_prefix: str, *parts: Hashable) -> tuple[Hashable, ...]:
    """The cache key of an org-scoped read."""
    return ("org", org_prefix, *parts)


def _encode(payload: Any) -> tuple[bytes, str]:
    """The JSON body as jsonify writes it, and its ETag."""
    body = (current_app.json.dumps(payload) + "\n").encode()
    return body, hashlib.sha256(body).hexdigest()[:32]


def conditional_json(body: bytes, etag: str) -> Response:
    """A 200 JSON response with an ETag, or 304 when If-None-Match has the same ETag."""
    response = Response(body, mimetype="application/json")
    response.set_etag(etag)
    response.headers["Cache-Control"] = "private, no-cache"
    response.vary.add("Authorization")
    response.vary.add("Cookie")
    response.make_conditional(request)
    return response


def cached_json(key: tuple[Hashable, ...], ttl: float, build: Callable[[], Any]) -> Response:
    """The JSON response of build(), kept for ttl seconds under key. Concurrent misses run build() once."""
    body, etag = cache.get_or_compute(key, ttl, lambda: _encode(build()))
    return conditional_json(body, etag)


def register_cache_invalidation(app: Flask) -> None:
    """Drop every cached org read after a successful API write in this process."""

    @app.after_request
    def _invalidate(response):
        if request.method in WRITE_METHODS and response.status_code < 400 and request.path.startswith("/api/"):
            dropped = cache.invalidate("org")
            if dropped:
                logger.debug("cache invalidated entries=%s path=%s", dropped, request.path)
        return response
