"""core.net: requests to a URL from a user connect only to an address that passed the public check."""

import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from core import net

REAL_GETADDRINFO = socket.getaddrinfo
# The Host header of each request that the test server answered
HOSTS: list[str] = []


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        HOSTS.append(str(self.headers.get("Host")))
        body = b'{"results": []}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.do_GET()

    def log_message(self, format, *args):
        pass


@pytest.fixture
def server():
    """An HTTP server on 127.0.0.1 that records the Host header of each request."""
    HOSTS.clear()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def rebind(monkeypatch):
    """rebind.test resolves to a public address the first time and to 127.0.0.1 after that."""
    calls = {"count": 0}

    def getaddrinfo(host, port, *args, **kwargs):
        if host != "rebind.test":
            return REAL_GETADDRINFO(host, port, *args, **kwargs)
        calls["count"] += 1
        address = "93.184.216.34" if calls["count"] == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("no_proxy", "*")
    return calls


def test_connection_uses_the_checked_address(server, monkeypatch):
    port = server.server_address[1]

    def public_addresses(host, port):
        assert host == "pinned.test"
        return ["127.0.0.1"]

    def getaddrinfo(host, port, *args, **kwargs):
        if host == "pinned.test":
            raise socket.gaierror("a second lookup of pinned.test")
        return REAL_GETADDRINFO(host, port, *args, **kwargs)

    monkeypatch.setattr(net, "public_addresses", public_addresses)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    response = net.get(f"http://pinned.test:{port}/", timeout=5)
    assert response.status_code == 200
    assert HOSTS == [f"pinned.test:{port}"]


def test_get_refuses_a_private_address():
    with pytest.raises(net.NotPublic):
        net.get("http://127.0.0.1:9/", timeout=5)


def test_uptime_probe_refuses_a_rebound_address(server, rebind):
    from modules.uptime import probe

    result = probe.fetch(f"http://rebind.test:{server.server_address[1]}/", 5)
    assert result.status_code is None and "non-public" in (result.error or "")
    assert HOSTS == []


def test_knowledge_fetch_refuses_a_rebound_address(server, rebind):
    from modules.knowledge import fetch

    with pytest.raises(fetch.FetchRejected):
        fetch.fetch_http(f"http://rebind.test:{server.server_address[1]}/")
    assert HOSTS == []


def test_firecrawl_of_an_org_refuses_a_rebound_address(server, rebind):
    from modules.knowledge import fetch

    firecrawl = fetch.Firecrawl(f"http://rebind.test:{server.server_address[1]}", public_only=True)
    with pytest.raises(fetch.FetchRejected):
        fetch.fetch_firecrawl("https://example.com/", firecrawl)
    assert HOSTS == []


def test_searxng_of_an_org_refuses_a_rebound_address(server, rebind):
    from modules.knowledge import fetch
    from modules.knowledge.content import search

    with pytest.raises(fetch.FetchRejected):
        search.search_json(f"http://rebind.test:{server.server_address[1]}/search?q=x&format=json", True)
    assert HOSTS == []


def test_embedder_of_an_org_refuses_a_rebound_address(server, rebind):
    from modules.knowledge import embedder

    service = embedder.Embedder(url=f"http://rebind.test:{server.server_address[1]}/v1", model="m", public_only=True)
    with pytest.raises(embedder.EmbeddingError):
        service.embed(["text"])
    assert HOSTS == []


@pytest.mark.parametrize("address", ["::ffff:127.0.0.1", "64:ff9b::7f00:1", "64:ff9b::a00:1", "2002:7f00:1::1"])
def test_an_ipv6_address_with_a_private_ipv4_inside_is_refused(address, monkeypatch):
    def getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port, 0, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    with pytest.raises(net.NotPublic):
        net.public_addresses("embedded.test", 80)


def test_a_public_ipv6_address_with_a_public_ipv4_inside_passes(monkeypatch):
    def getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::808:808", port, 0, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    assert net.public_addresses("nat64.test", 80) == ["64:ff9b::808:808"]


def test_a_timeout_on_the_first_address_tries_the_next(server, monkeypatch):
    port = server.server_address[1]
    tried: list[str] = []
    real = net.create_connection

    def create_connection(address, *args, **kwargs):
        tried.append(address[0])
        if address[0] == "192.0.2.1":
            raise TimeoutError("timed out")
        return real(address, *args, **kwargs)

    monkeypatch.setattr(net, "public_addresses", lambda host, port: ["192.0.2.1", "127.0.0.1"])
    monkeypatch.setattr(net, "create_connection", create_connection)
    response = net.get(f"http://two.test:{port}/", timeout=5)
    assert response.status_code == 200
    assert tried == ["192.0.2.1", "127.0.0.1"]


def test_a_timeout_on_every_address_is_a_connect_timeout(monkeypatch):
    import requests

    def create_connection(address, *args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(net, "public_addresses", lambda host, port: ["192.0.2.1", "192.0.2.2"])
    monkeypatch.setattr(net, "create_connection", create_connection)
    with pytest.raises(requests.exceptions.ConnectTimeout):
        net.get("http://slow.test/", timeout=1)


def test_the_ca_bundle_from_the_environment_is_used(monkeypatch):
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/etc/ssl/custom.pem")
    assert net._session().verify == "/etc/ssl/custom.pem"
    monkeypatch.delenv("REQUESTS_CA_BUNDLE")
    monkeypatch.delenv("CURL_CA_BUNDLE", raising=False)
    assert net._session().verify is True


def test_a_cookie_from_one_call_is_not_sent_with_the_next(monkeypatch):
    import http.server

    cookies: list[str | None] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            cookies.append(self.headers.get("Cookie"))
            self.send_response(200)
            self.send_header("Set-Cookie", "org=one; Path=/")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setattr(net, "public_addresses", lambda host, port: ["127.0.0.1"])
        url = f"http://cookie.test:{httpd.server_address[1]}/"
        net.get(url, timeout=5)
        net.get(url, timeout=5)
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert cookies == [None, None]
