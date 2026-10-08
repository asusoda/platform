"""Fetching pages for crawled sources: robots.txt, per-host pacing, public addresses only. No Flask here.

Ported from SparkyAI's scraper (apps/scraper/ingest/fetch.py, robots.py, pace.py). Pages come
through self-hosted Firecrawl when FIRECRAWL_URL is set (JavaScript rendered, markdown out), else
through a plain GET. Every URL, and every redirect, must resolve to a public address, so a source
cannot make the platform read its own network.
"""

import ipaddress
import os
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = os.environ.get("KNOWLEDGE_USER_AGENT", "PlatformKnowledgeBot/1.0")
TIMEOUT_SECONDS = 30
MAX_BYTES = 10_000_000
MAX_REDIRECTS = 5
ROBOTS_CACHE_SECONDS = 3600


class FetchError(RuntimeError):
    """The page could not be fetched now; a later run may succeed."""


class FetchRejected(RuntimeError):
    """The page must not or cannot be fetched: robots.txt, a 4xx, a private address, too large."""


@dataclass(frozen=True)
class _Response:
    url: str
    status: int
    body: bytes
    content_type: str


@dataclass(frozen=True)
class Fetched:
    url: str
    body: bytes
    content_type: str
    title: str | None = None
    text: str | None = None  # set when the fetcher already produced clean text


def check_url(url: str) -> None:
    """Raise FetchRejected unless url is http(s) on a host that resolves only to public addresses."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchRejected(f"Only http and https URLs can be fetched: {url}")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as e:
        raise FetchError(f"{parts.hostname} does not resolve") from e
    for info in infos:
        address = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if not address.is_global:
            raise FetchRejected(f"{parts.hostname} resolves to a non-public address")


def _get(url: str, *, limit: int = MAX_BYTES) -> _Response:
    """GET with redirects followed by hand, so each hop is checked. The body is read up to limit."""
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT_SECONDS,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as e:
            raise FetchError(f"{url} could not be reached") from e
        if response.is_redirect and response.headers.get("location"):
            url = urljoin(url, response.headers["location"])
            response.close()
            continue
        body = bytearray()
        for piece in response.iter_content(65536):
            body.extend(piece)
            if len(body) > limit:
                response.close()
                raise FetchRejected(f"{url} is larger than {limit} bytes")
        return _Response(url, response.status_code, bytes(body), response.headers.get("content-type", ""))
    raise FetchRejected(f"{url} redirects more than {MAX_REDIRECTS} times")


def robots_allowed(url: str) -> bool:
    parts = urlsplit(url)
    window = int(time.time() // ROBOTS_CACHE_SECONDS)
    return _robots(f"{parts.scheme}://{parts.netloc}", window).can_fetch(USER_AGENT, url)


@lru_cache(maxsize=256)
def _robots(origin: str, window: int) -> RobotFileParser:
    response = _get(f"{origin}/robots.txt", limit=500_000)
    return robots_rules(response.status, response.body.decode("utf-8", "replace"))


def robots_rules(status: int, body: str) -> RobotFileParser:
    """Rules from one robots.txt response. 4xx allows everything; 5xx means try again later."""
    if status >= 500:
        raise FetchError(f"robots.txt returned {status}")
    parser = RobotFileParser()
    parser.parse(["User-agent: *", "Allow: /"] if status >= 400 else body.splitlines())
    return parser


def fetch_http(url: str) -> Fetched:
    response = _get(url)
    if response.status >= 500:
        raise FetchError(f"{url} returned {response.status}")
    if response.status >= 400:
        raise FetchRejected(f"{url} returned {response.status}")
    return Fetched(url=response.url, body=response.body, content_type=response.content_type)


def parse_firecrawl(url: str, payload: Any) -> Fetched:
    """A page from a Firecrawl /v2/scrape response."""
    if not isinstance(payload, dict) or not payload.get("success"):
        raise FetchError(f"Firecrawl failed for {url}")
    data = payload.get("data")
    meta = data.get("metadata") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(meta, dict) or "statusCode" not in meta:
        raise FetchError(f"Firecrawl sent no page for {url}")
    status = int(meta["statusCode"])
    if status >= 400:
        raise FetchRejected(f"{url} returned {status}")
    markdown = data.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise FetchError(f"Firecrawl returned no text for {url}")
    title = meta.get("title")
    return Fetched(
        url=str(meta.get("url") or meta.get("sourceURL") or url),
        body=markdown.encode(),
        content_type="text/markdown",
        title=title if isinstance(title, str) else None,
        text=markdown,
    )


def fetch_firecrawl(url: str, base_url: str) -> Fetched:
    key = os.environ.get("FIRECRAWL_API_KEY", "")
    try:
        response = requests.post(
            base_url.rstrip("/") + "/v2/scrape",
            json={"url": url, "formats": ["markdown"], "onlyMainContent": True, "timeout": 60000},
            headers={"Authorization": f"Bearer {key}"} if key else {},
            timeout=90,
        )
    except requests.RequestException as e:
        raise FetchError("Firecrawl could not be reached") from e
    if response.status_code >= 500:
        raise FetchError(f"Firecrawl returned {response.status_code}")
    if response.status_code >= 400:
        raise FetchRejected(f"Firecrawl returned {response.status_code}")
    try:
        return parse_firecrawl(url, response.json())
    except ValueError as e:
        raise FetchError(f"Firecrawl sent a body that is not JSON for {url}") from e


def fetch(url: str) -> Fetched:
    """A page that robots.txt allows us to read."""
    check_url(url)
    if not robots_allowed(url):
        raise FetchRejected(f"robots.txt disallows {url}")
    firecrawl = os.environ.get("FIRECRAWL_URL", "").strip()
    return fetch_firecrawl(url, firecrawl) if firecrawl else fetch_http(url)


class HostPacer:
    """Holds each fetch until gap seconds have passed since the last fetch to the same host."""

    def __init__(
        self,
        gap: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._gap = gap
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str) -> None:
        host = urlsplit(url).hostname or ""
        with self._lock:
            now = self._clock()
            last = self._last.get(host)
            slot = now if self._gap <= 0 or last is None else max(now, last + self._gap)
            self._last[host] = slot
        if slot > now:
            self._sleep(slot - now)
