"""core.browser: every request of a page is answered from Python through core.net. No browser and no network."""

from dataclasses import dataclass, field
from typing import Any

import pytest
import requests

from core import browser, net


@dataclass
class FakeRequest:
    url: str
    method: str = "GET"
    resource_type: str = "document"
    post_data_buffer: bytes | None = None
    headers: dict = field(default_factory=lambda: {"cookie": "s=1", "host": "x", "user-agent": "ua"})

    def all_headers(self) -> dict:
        return self.headers


class FakeRoute:
    def __init__(self, request: FakeRequest):
        self.request = request
        self.done: tuple | None = None

    def continue_(self):
        self.done = ("continue",)

    def abort(self, code: str = "failed"):
        self.done = ("abort", code)

    def fulfill(self, **kwargs):
        self.done = ("fulfill", kwargs)


class FakeRaw:
    """The urllib3 response: its headers keep each set-cookie line."""

    def __init__(self, cookies: list[str]):
        from urllib3 import HTTPHeaderDict

        self.headers = HTTPHeaderDict()
        for cookie in cookies:
            self.headers.add("set-cookie", cookie)


def _response(status: int = 200, body: bytes = b"<html>ok</html>", headers: dict | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.headers.update({"content-type": "text/html", "content-length": str(len(body)), **(headers or {})})
    response.raw = FakeRaw(["a=1", "b=2"] if "set-cookie" in (headers or {}) else [])
    response._content = body
    response._content_consumed = True
    return response


@pytest.fixture
def sent(monkeypatch):
    """net.request records each call and answers served["response"]."""
    served: dict[str, Any] = {"calls": [], "response": _response()}

    def fake_request(method, url, **kwargs):
        served["calls"].append((method, url, kwargs))
        if isinstance(served["response"], Exception):
            raise served["response"]
        return served["response"]

    monkeypatch.setattr(net, "request", fake_request)
    return served


def test_a_request_is_fetched_in_python_and_fulfilled(sent):
    route = FakeRoute(FakeRequest("https://example.edu/"))
    browser.answer(route)
    assert route.done is not None and route.done[0] == "fulfill"
    assert route.done[1]["status"] == 200 and route.done[1]["body"] == b"<html>ok</html>"
    assert "content-length" not in route.done[1]["headers"]
    method, url, kwargs = sent["calls"][0]
    assert (method, url) == ("GET", "https://example.edu/")
    assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
    assert kwargs["headers"] == {"cookie": "s=1", "user-agent": "ua"}


def test_a_redirect_goes_back_to_the_browser(sent):
    sent["response"] = _response(302, b"", {"location": "http://127.0.0.1:8000/health", "set-cookie": "a=1"})
    route = FakeRoute(FakeRequest("https://example.edu/"))
    browser.answer(route)
    assert route.done is not None and route.done[0] == "fulfill"
    headers = route.done[1]["headers"]
    assert route.done[1]["status"] == 302 and headers["location"] == "http://127.0.0.1:8000/health"
    assert headers["set-cookie"] == "a=1\nb=2"
    assert len(sent["calls"]) == 1, "the redirect is not followed in Python"


@pytest.mark.parametrize("error", [net.NotPublic("private"), net.NoHost("api does not resolve")])
def test_a_private_or_unknown_host_is_aborted(sent, error):
    sent["response"] = error
    route = FakeRoute(FakeRequest("http://api:8000/health"))
    browser.answer(route)
    assert route.done == ("abort", "addressunreachable")


def test_the_real_check_refuses_loopback():
    route = FakeRoute(FakeRequest("http://127.0.0.1:8000/health"))
    browser.answer(route)
    assert route.done == ("abort", "addressunreachable")


def test_data_urls_pass_and_heavy_types_are_skipped(sent):
    data = FakeRoute(FakeRequest("data:text/plain,hi"))
    browser.answer(data)
    assert data.done == ("continue",)
    image = FakeRoute(FakeRequest("https://example.edu/a.png", resource_type="image"))
    browser.answer(image)
    assert image.done == ("abort", "failed")
    assert sent["calls"] == []


def test_a_body_over_the_cap_is_aborted(sent):
    sent["response"] = _response(body=b"x" * 2000)
    route = FakeRoute(FakeRequest("https://example.edu/"))
    browser.answer(route, max_bytes=1000)
    assert route.done == ("abort", "failed")


class FakeContext:
    def __init__(self):
        self.handler = None
        self.ws_handler = None

    def route(self, pattern, handler):
        self.handler = handler

    def route_web_socket(self, pattern, handler):
        self.ws_handler = handler


def test_guard_routes_every_request_caps_them_and_closes_websockets(sent):
    context = FakeContext()
    browser.guard(context, max_requests=2)
    routes = [FakeRoute(FakeRequest(f"https://example.edu/{i}")) for i in range(3)]
    for route in routes:
        assert context.handler is not None
        context.handler(route)
    assert [r.done[0] for r in routes if r.done] == ["fulfill", "fulfill", "abort"]

    class Socket:
        closed = False

        def close(self):
            self.closed = True

    ws = Socket()
    assert context.ws_handler is not None
    context.ws_handler(ws)
    assert ws.closed


@pytest.mark.parametrize("url", ["ws://browser:3000/", "ws://browser:3000", "ws://browser:3000/unset"])
def test_a_server_url_without_a_secret_path_is_refused(url):
    with pytest.raises(browser.BrowserConfigError), browser.open_browser(object(), url):
        pass


def test_connect_sends_the_dead_proxy_and_local_launch_uses_it_too(monkeypatch):
    calls: list[tuple] = []

    class Chromium:
        def connect(self, url, **kwargs):
            calls.append(("connect", url, kwargs))
            return Closable()

        def launch(self, **kwargs):
            calls.append(("launch", kwargs))
            return Closable()

    class Closable:
        def close(self):
            calls.append(("close",))

    class Playwright:
        chromium = Chromium()

    with browser.open_browser(Playwright(), "ws://browser:3000/s3cret"):
        pass
    monkeypatch.delenv("BROWSER_URL", raising=False)
    with browser.open_browser(Playwright()):
        pass
    connect, close, launch, _ = calls
    assert connect[1] == "ws://browser:3000/s3cret"
    assert "--proxy-server=http://127.0.0.1:9" in connect[2]["headers"]["x-playwright-launch-options"]
    assert launch[1]["args"] == browser.ARGS and close == ("close",)
