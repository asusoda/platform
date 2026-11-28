"""The browser that loads pages that need JavaScript: the shared Playwright server, or a local Chromium. No Flask here.

open_browser() connects to BROWSER_URL, or starts Chromium on this machine when it is unset. BROWSER_URL must have
a secret path (ws://browser:3000/<BROWSER_SECRET>), so a page in the browser cannot start its own browser on the
Playwright server. At most BROWSER_MAX_PAGES browsers are open at one time in a process; the others wait.

guard(context) answers every request of a browser context from Python, through core.net. The browser itself never
connects: a page reaches public addresses only, also when DNS answers change, and never the API, MCP server or
host. Chromium starts with a proxy that goes nowhere, so a request that the guard does not see fails. WebSockets
are closed. Playwright is imported only when a function runs.
"""

import importlib
import json
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlsplit

import requests

from core import net
from core.log import get_logger

logger = get_logger(__name__)

CONNECT_MS = 10_000
# Chromium sends every request to a proxy that does not exist; the guard answers them before that.
ARGS = ["--proxy-server=http://127.0.0.1:9", "--webrtc-ip-handling-policy=disable_non_proxied_udp"]
SKIPPED = frozenset({"image", "media", "font"})
MAX_BYTES = 10_000_000
MAX_REQUESTS = 200
REQUEST_TIMEOUT = (5, 20)
# Headers that requests sets itself, and response headers that no longer match the decoded body
DROP_REQUEST = frozenset({"host", "content-length", "connection", "accept-encoding"})
DROP_RESPONSE = frozenset({"content-encoding", "content-length", "transfer-encoding", "connection"})
MISSING_PATH = "Set BROWSER_SECRET and put it in the BROWSER_URL path, such as ws://browser:3000/<BROWSER_SECRET>"


class BrowserConfigError(ValueError):
    """BROWSER_URL is set without a secret path."""


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


_open = threading.BoundedSemaphore(_env_int("BROWSER_MAX_PAGES", 2))


def server_url() -> str:
    """The Playwright server of the deployment, or an empty string when there is none."""
    return os.environ.get("BROWSER_URL", "").strip()


def url_problem(url: str) -> str | None:
    """Why the BROWSER_URL cannot be used, or None. The path must be a secret, not / or /unset."""
    path = urlsplit(url).path.strip("/")
    if not path or path == "unset":
        return MISSING_PATH
    return None


def api() -> Any:
    """playwright.sync_api, imported on first use."""
    return importlib.import_module("playwright.sync_api")


@contextmanager
def open_browser(playwright: Any, server: str | None = None) -> Iterator[Any]:
    """A headless Chromium: the shared browser at server (default BROWSER_URL), else a local one.

    Raises BrowserConfigError when the server URL has no secret path, and the Playwright error when it
    cannot connect. Waits while BROWSER_MAX_PAGES browsers are open in this process.
    """
    url = server_url() if server is None else server
    if url and (problem := url_problem(url)):
        raise BrowserConfigError(problem)
    with _open:
        if url:
            options = json.dumps({"args": ARGS})
            browser = playwright.chromium.connect(
                url, timeout=CONNECT_MS, headers={"x-playwright-launch-options": options}
            )
        else:
            browser = playwright.chromium.launch(headless=True, args=ARGS)
        try:
            yield browser
        finally:
            browser.close()


def _request_headers(request: Any) -> dict[str, str]:
    return {k: v for k, v in request.all_headers().items() if k.lower() not in DROP_REQUEST and not k.startswith(":")}


def _response_headers(response: requests.Response) -> dict[str, str]:
    headers = {k: v for k, v in response.headers.items() if k.lower() not in DROP_RESPONSE}
    raw = getattr(response.raw, "headers", None)
    cookies = raw.getlist("set-cookie") if raw is not None and hasattr(raw, "getlist") else []
    if cookies:
        # Playwright splits set-cookie on new lines
        headers = {k: v for k, v in headers.items() if k.lower() != "set-cookie"} | {"set-cookie": "\n".join(cookies)}
    return headers


def _read(response: requests.Response, max_bytes: int) -> bytes | None:
    """The body, or None when it is larger than max_bytes."""
    body = bytearray()
    for chunk in response.iter_content(64 * 1024):
        body.extend(chunk)
        if len(body) > max_bytes:
            return None
    return bytes(body)


def answer(route: Any, max_bytes: int = MAX_BYTES) -> None:
    """Answer one request of the browser: fetch it with core.net and fulfill it, or abort it."""
    request = route.request
    url = request.url
    if url.startswith(("data:", "blob:")):
        route.continue_()
        return
    if request.resource_type in SKIPPED:
        route.abort()
        return
    try:
        response = net.request(
            request.method,
            url,
            headers=_request_headers(request),
            data=request.post_data_buffer,
            allow_redirects=False,
            stream=True,
            timeout=REQUEST_TIMEOUT,
        )
    except (net.NotPublic, net.NoHost) as e:
        logger.info("browser request refused url=%s reason=%s", url[:200], e)
        route.abort("addressunreachable")
        return
    except requests.RequestException as e:
        logger.info("browser request failed url=%s error=%s", url[:200], type(e).__name__)
        route.abort()
        return
    try:
        body = _read(response, max_bytes)
    except requests.RequestException:
        route.abort()
        return
    finally:
        response.close()
    if body is None:
        logger.info("browser response too large url=%s", url[:200])
        route.abort()
        return
    route.fulfill(status=response.status_code, headers=_response_headers(response), body=body)


def guard(context: Any, max_bytes: int = MAX_BYTES, max_requests: int = MAX_REQUESTS) -> None:
    """Route every request of context through answer(), at most max_requests of them, and close every WebSocket."""
    count = {"n": 0}

    def handler(route: Any) -> None:
        count["n"] += 1
        if count["n"] > max_requests:
            route.abort()
            return
        answer(route, max_bytes)

    context.route("**/*", handler)
    context.route_web_socket("**/*", lambda ws: ws.close())
