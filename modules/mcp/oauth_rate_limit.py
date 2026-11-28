"""The limit of requests of each client IP on the OAuth routes of the MCP server, as ASGI middleware."""

import json
import threading
import time

# Requests of one client IP in a window, by the path under the public URL: (count, seconds)
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/register": (10, 3600),
    "/authorize": (30, 60),
    "/oauth": (30, 60),
    "/token": (60, 60),
    "/revoke": (30, 60),
}


class RateLimit:
    """ASGI middleware: at most RATE_LIMITS requests of one client IP in a window. Counts in this process.

    The client IP is the address that uvicorn gives. Behind a reverse proxy, set FORWARDED_ALLOW_IPS to
    the proxy's address, so that uvicorn uses X-Forwarded-For.
    """

    MAX_KEYS = 50000

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")
        # One table per rule, so a flood on one route does not fill the table of another
        self.counts: dict[str, dict[str, tuple[int, int]]] = {rule: {} for rule in RATE_LIMITS}
        self.pruned: dict[str, float] = {}
        self.lock = threading.Lock()

    def _rule(self, path: str) -> str | None:
        if not path.startswith(self.prefix + "/"):
            return None
        rest = path[len(self.prefix) :]
        return next((r for r in RATE_LIMITS if rest == r or rest.startswith(r + "/")), None)

    def allow(self, rule: str, ip: str, now: float | None = None) -> int:
        """0 when the request may go on, else the seconds until the window ends."""
        count, seconds = RATE_LIMITS[rule]
        moment = time.time() if now is None else now
        window = int(moment // seconds)
        with self.lock:
            table = self.counts.setdefault(rule, {})
            if ip not in table and len(table) >= self.MAX_KEYS:
                # Prune at most once a second; while the table stays full, a new IP waits for the next window
                if moment - self.pruned.get(rule, 0.0) >= 1:
                    table = self.counts[rule] = {k: v for k, v in table.items() if v[0] == window}
                    self.pruned[rule] = moment
                if len(table) >= self.MAX_KEYS:
                    return max(1, int((window + 1) * seconds - moment))
            seen_window, seen = table.get(ip, (window, 0))
            used = seen if seen_window == window else 0
            if used >= count:
                return max(1, int((window + 1) * seconds - moment))
            table[ip] = (window, used + 1)
        return 0

    async def __call__(self, scope, receive, send):
        rule = self._rule(scope.get("path", "")) if scope["type"] == "http" else None
        if rule is None:
            await self.app(scope, receive, send)
            return
        client = scope.get("client") or ("unknown", 0)
        wait = self.allow(rule, str(client[0]))
        if not wait:
            await self.app(scope, receive, send)
            return
        body = json.dumps({"error": "too_many_requests", "error_description": "Too many requests. Try again later"})
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(wait).encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body.encode()})
