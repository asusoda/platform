"""One log line per API request: which route, which org, which kind of credential, and from where.

The lines show who still uses app tokens and which officers act across orgs, before the
phase 1 access checks start refusing anything. No token, cookie or request body is logged.
"""

import time
from urllib.parse import urlparse

import jwt
from flask import Flask, g, request, session

from core.log import get_logger

logger = get_logger("request_log")

SKIPPED_PATHS = ("/health", "/build/", "/api/public/static/", "/api/public/favicon.ico")


def bearer_token() -> str | None:
    """The token of an Authorization: Bearer header, or None."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer ") and header[7:].strip():
        return header[7:].strip()
    return None


def credential(token_manager) -> tuple[str, str | None]:
    """Classify the request's credential and return (kind, discord_id)."""
    token = bearer_token()
    if token is None:
        if session.get("token") or session.get("discord_id"):
            return "session", session.get("discord_id")
        return "none", None
    if token.startswith("plat_"):
        return "machine", None
    try:
        claims = jwt.decode(
            token,
            token_manager.public_key,
            algorithms=[token_manager.algorithm],
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError:
        # Not signed by this server: a Clerk session token or garbage.
        return "external", None
    if "app_name" in claims:
        return "app", None
    return str(claims.get("type", "untyped")), claims.get("discord_id")


def org_from_request() -> str | None:
    args = request.view_args or {}
    for key in ("org_prefix", "org_id", "guild_id"):
        if key in args:
            return str(args[key])
    return request.headers.get("X-Organization-Prefix") or request.headers.get("X-Organization-ID")


def _origin() -> str | None:
    source = request.headers.get("Origin") or request.headers.get("Referer")
    if not source:
        return None
    return urlparse(source).netloc or None


def register_request_logging(app: Flask, token_manager) -> None:
    """Log a structured line after every API request."""

    @app.before_request
    def _start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def _log_request(response):
        if request.path.startswith(SKIPPED_PATHS) or not request.path.startswith("/api/"):
            return response
        try:
            kind, discord_id = credential(token_manager)
            started = g.get("request_started")
            elapsed_ms = round((time.perf_counter() - started) * 1000) if started else None
            route = request.url_rule.rule if request.url_rule else request.path
            logger.info(
                "request method=%s route=%s status=%s org=%s credential=%s discord_id=%s origin=%s ms=%s",
                request.method,
                route,
                response.status_code,
                org_from_request(),
                kind,
                discord_id,
                _origin(),
                elapsed_ms,
            )
        except Exception:
            logger.exception("request logging failed")
        return response
